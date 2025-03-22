"""
RAG module
"""

from ...models import Models

from ..base import Pipeline
from ..data import Tokenizer
from ..text import Questions
from ..text import Similarity

from .factory import GenerationFactory
from .llm import LLM


class RAG(Pipeline):
    """
    Extracts knowledge from content by joining a prompt, context data store and generative model together. The data store can be
    an embeddings database or a similarity instance with associated input text. The generative model can be a prompt-driven large
    language model (LLM), an extractive question-answering model or a custom pipeline. This is known as retrieval augmented generation (RAG).
    """

    # pylint: disable=R0913
    def __init__(
        self,
        similarity,
        path,
        quantize=False,
        gpu=True,
        model=None,
        tokenizer=None,
        minscore=None,
        mintokens=None,
        context=None,
        task=None,
        output="default",
        template=None,
        separator=" ",
        system=None,
        **kwargs,
    ):
        """
        Builds a new RAG pipeline.

        Args:
            similarity: similarity instance (embeddings or similarity pipeline)
            path: path to model, supports a LLM, Questions or custom pipeline
            quantize: True if model should be quantized before inference, False otherwise.
            gpu: if gpu inference should be used (only works if GPUs are available)
            model: optional existing pipeline model to wrap
            tokenizer: Tokenizer class
            minscore: minimum score to include context match, defaults to None
            mintokens: minimum number of tokens to include context match, defaults to None
            context: topn context matches to include, defaults to 3
            task: model task (language-generation, sequence-sequence or question-answering), defaults to auto-detect
            output: output format, 'default' returns (name, answer), 'flatten' returns answers and 'reference' returns (name, answer, reference)
            template: prompt template, it must have a parameter for {question} and {context}, defaults to "{question} {context}"
            separator: context separator
            system: system prompt, defaults to None
            kwargs: additional keyword arguments to pass to pipeline model
        """

        # Similarity instance
        self.similarity = similarity

        # Model can be a LLM, Questions or custom pipeline
        self.model = self.load(path, quantize, gpu, model, task, **kwargs)

        # Tokenizer class use default method if not set
        self.tokenizer = tokenizer if tokenizer else Tokenizer() if hasattr(self.similarity, "scoring") and self.similarity.isweighted() else None

        # Minimum score to include context match
        self.minscore = minscore if minscore is not None else 0.0

        # Minimum number of tokens to include context match
        self.mintokens = mintokens if mintokens is not None else 0.0

        # Top n context matches to include for context
        self.context = context if context else 3

        # Output format
        self.output = output

        # Prompt template
        self.template = template if template else "{question} {context}"

        # Context separator
        self.separator = separator

        # System prompt template
        self.system = system

    def __call__(self, queue, texts=None, **kwargs):
        """
        Finds answers to input questions. This method runs queries to find the top n best matches and uses that as the context.
        A model is then run against the context for each input question, with the answer returned.

        Args:
            queue: input question queue (name, query, question, snippet), can be list of tuples/dicts/strings or a single input element
            texts: optional list of text for context, otherwise runs embeddings search
            kwargs: additional keyword arguments to pass to pipeline model

        Returns:
            list of answers matching input format (tuple or dict) containing fields as specified by output format
        """

        # Save original queue format
        inputs = queue

        # Convert queue to list, if necessary
        queue = queue if isinstance(queue, list) else [queue]

        # Convert dictionary inputs to tuples
        if queue and isinstance(queue[0], dict):
            # Convert dict to tuple
            queue = [tuple(row.get(x) for x in ["name", "query", "question", "snippet"]) for row in queue]

        if queue and isinstance(queue[0], str):
            # Convert string questions to tuple
            queue = [(None, row, row, None) for row in queue]

        # Rank texts by similarity for each query
        results = self.query([query for _, query, _, _ in queue], texts)

        # Build question-context pairs
        names, queries, questions, contexts, topns, snippets = [], [], [], [], [], []
        for x, (name, query, question, snippet) in enumerate(queue):
            # Get top n best matching segments
            topn = sorted(results[x], key=lambda y: y[2], reverse=True)[: self.context]

            # Generate context using ordering from texts, if available, otherwise order by score
            context = self.separator.join(text for _, text, _ in (sorted(topn, key=lambda y: y[0]) if texts else topn))

            names.append(name)
            queries.append(query)
            questions.append(question)
            contexts.append(context)
            topns.append(topn)
            snippets.append(snippet)

        # Run pipeline and return answers
        answers = self.answers(questions, contexts, **kwargs)

        # Apply output formatting to answers and return
        return self.apply(inputs, names, queries, answers, topns, snippets) if isinstance(answers, list) else answers

    def load(self, path, quantize, gpu, model, task, **kwargs):
        """
        Loads a LLM, Questions or custom pipeline.

        Args:
            path: path to model, supports a LLM, Questions or custom pipeline
            quantize: True if model should be quantized before inference, False otherwise.
            gpu: if gpu inference should be used (only works if GPUs are available)
            model: optional existing pipeline model to wrap
            task: model task (language-generation, sequence-sequence or question-answering), defaults to auto-detect
            kwargs: additional keyword arguments to pass to pipeline model

        Returns:
            LLM, Questions or custom pipeline
        """

        # Only try to load if path is a string
        if not isinstance(path, str):
            return path

        # Attempt to resolve task if not provided
        task = GenerationFactory.method(path, task)
        task = Models.task(path, **kwargs) if task == "transformers" else task

        # Load Questions pipeline
        if task == "question-answering":
            return Questions(path, quantize, gpu, model, **kwargs)

        # Load LLM pipeline
        return LLM(path=path, quantize=quantize, gpu=gpu, model=model, task=task, **kwargs)

    def query(self, queries, texts):
        """
        Rank texts by similarity for each query. If texts is empty, an embeddings search will be executed.
        Returns results sorted by best match.

        Args:
            queries: list of queries
            texts: optional list of text

        Returns:
            list of (id, data, score) per query
        """

        if not queries:
            return []

        # Score text against queries
        scores, segments, tokenlist = self.score(queries, texts)

        # Build question-context pairs
        results = []
        for i, query in enumerate(queries):
            # Get list of required and prohibited tokens
            must = [token.strip("+") for token in query.split() if token.startswith("+") and len(token) > 1]
            mnot = [token.strip("-") for token in query.split() if token.startswith("-") and len(token) > 1]

            # Segment text is static when texts is passed in but different per query when an embeddings search is run
            segment = segments if texts else segments[i]
            tokens = tokenlist if texts else tokenlist[i]

            # List of matches
            matches = []
            for y, (x, score) in enumerate(scores[i]):
                # Segments and tokens are statically ordered when texts is passed in, need to resolve values with score id
                # Scores, segments and tokens all share the same list ordering when an embeddings search is run
                x = x if texts else y

                # Get segment text
                text = segment[x][1]

                # Add result if:
                #   - all required tokens are present or there are not required tokens AND
                #   - all prohibited tokens are not present or there are not prohibited tokens
                #   - score is above minimum score required
                #   - number of tokens is above minimum number of tokens required
                if (not must or all(token.lower() in text.lower() for token in must)) and (
                    not mnot or all(token.lower() not in text.lower() for token in mnot)
                ):
                    if score >= self.minscore and len(tokens[x]) >= self.mintokens:
                        matches.append(segment[x] + (score,))

            # Add query matches sorted by highest score
            results.append(matches)

        return results

    def score(self, queries, texts):
        """
        Runs queries against texts (or an embeddings search if texts is empty) and builds list of
        similarity scores for each query-text combination.

        Args:
            queries: list of queries
            texts: optional list of text

        Returns:
            scores, segments, tokenlist
        """

        # Tokenize text
        segments, tokenlist = [], []
        if texts:
            for text in texts:
                # Run tokenizer method, if available, otherwise returns original text
                tokens = self.tokenize(text)
                if tokens:
                    segments.append(text)
                    tokenlist.append(tokens)

            # Add index id to segments to preserve ordering after filters
            segments = list(enumerate(segments))

        # Get list of (id, score) - sorted by highest score per query
        if isinstance(self.similarity, Similarity):
            # Score using similarity pipeline
            scores = self.similarity(queries, [t for _, t in segments])
        elif texts:
            # Score using embeddings.batchsimilarity
            scores = self.similarity.batchsimilarity([self.tokenize(x) for x in queries], tokenlist)
        else:
            # Score using embeddings.batchsearch
            scores, segments, tokenlist = self.batchsearch(queries)

        return scores, segments, tokenlist

    def batchsearch(self, queries):
        """
        Runs a batch embeddings search for a set of queries.

        Args:
            queries: list of queries to run

        Returns:
            scores, segments, tokenlist
        """

        scores, segments, tokenlist = [], [], []
        for results in self.similarity.batchsearch([self.tokenize(x) for x in queries], self.context):
            # Assume embeddings content is enabled and results are dictionaries
            scores.append([(result["id"], result["score"]) for result in results])
            segments.append([(result["id"], result["text"]) for result in results])
            tokenlist.append([self.tokenize(result["text"]) for result in results])

        return scores, segments, tokenlist

    def tokenize(self, text):
        """
        Tokenizes text. Returns original text if tokenizer is not available.

        Args:
            text: input text

        Returns:
            tokens if tokenizer available otherwise original text
        """

        return self.tokenizer(text) if self.tokenizer else text

    def answers(self, questions, contexts, **kwargs):
        """
        Executes pipeline and formats extracted answers.

        Args:
            questions: questions
            contexts: question context
            kwargs: additional keyword arguments to pass to model

        Returns:
            answers
        """

        # Run model inference with questions pipeline
        if isinstance(self.model, Questions):
            return self.model(questions, contexts)

        # Run generator pipeline
        return self.model(self.prompts(questions, contexts), **kwargs)

    def prompts(self, questions, contexts):
        """
        Builds a list of prompts using the passed in questions and contexts.

        Args:
            questions: questions
            contexts: question context

        Returns:
            prompts
        """

        # Format prompts for generator pipeline
        prompts = []
        for x, context in enumerate(contexts):
            # Create input prompt
            prompt = self.template.format(question=questions[x], context=context)

            # Add system prompt, if necessary
            if self.system:
                prompt = [
                    {"role": "system", "content": self.system.format(question=questions[x], context=context)},
                    {"role": "user", "content": prompt},
                ]

            prompts.append(prompt)

        return prompts

    def apply(self, inputs, names, queries, answers, topns, snippets):
        """
        Applies the following formatting rules to answers.
            - each answer row matches input format (tuple or dict)
            - if output format is 'flatten' then this method flattens to a list of answers
            - if output format is 'reference' then a list of (name, answer, reference) is returned
            - otherwise, if output format is 'default' or anything else list of (name, answer) is returned

        Args:
            inputs: original inputs
            names: question identifiers/names
            queries: list of input queries
            answers: list of generated answers
            topns: top n records used for context
            snippets: flags to enable answer snippets per answer

        Returns:
            list of answers matching input format (tuple or dict) containing fields as specified by output format
        """

        # Resolve answers as snippets
        answers = self.snippets(names, answers, topns, snippets)

        # Flatten to list of answers and return
        if self.output == "flatten":
            answers = [answer for _, answer in answers]
        else:
            # Resolve id reference for each answer
            if self.output == "reference":
                answers = self.reference(queries, answers, topns)

            # Ensure output format matches input format
            first = inputs[0] if inputs and isinstance(inputs, list) else inputs
            if isinstance(first, (dict, str)):
                # Add name if input queue had name field
                fields = ["name", "answer", "reference"] if isinstance(first, dict) and "name" in first else [None, "answer", "reference"]
                answers = [{fields[x]: column for x, column in enumerate(row) if fields[x]} for row in answers]

        # Unpack single answer, if necessary
        return answers[0] if answers and isinstance(inputs, (tuple, dict, str)) else answers

    def snippets(self, names, answers, topns, snippets):
        """
        Extracts text surrounding the answer within context.

        Args:
            names: question identifiers/names
            answers: list of generated answers
            topns: top n records used for context
            snippets: flags to enable answer snippets per answer

        Returns:
            answers resolved as snippets per question, if necessary
        """

        # Extract and format answer
        results = []

        for x, answer in enumerate(answers):
            # Resolve snippet if necessary
            if answer and snippets[x]:
                # Searches for first text element to contain answer
                for _, text, _ in topns[x]:
                    if answer in text:
                        answer = text
                        break

            results.append((names[x], answer))

        return results

    def reference(self, queries, answers, topns):
        """
        Reference each answer with the best matching context element id.

        Args:
            queries: list of input queries
            answers: list of answers
            topn: top n context elements as (id, data, tag)

        Returns:
            list of (name, answer, reference)
        """

        # Convert queries to terms
        terms = self.terms(queries)

        outputs = []
        for x, (name, answer) in enumerate(answers):
            # Get matching topn
            topn, reference = topns[x], None

            if topn:
                # Build query from keyword terms and the answer text
                query = f"{terms[x]} {answers[x][1]}"

                # Compare answer to topns to find best match
                scores, _, _ = self.score([query], [text for _, text, _ in topn])

                # Get top score index
                index = scores[0][0][0]

                # Use matching topn id as reference
                reference = topn[index][0]

            # Append (name, answer, reference) tuple
            outputs.append((name, answer, reference))

        return outputs

    def terms(self, queries):
        """
        Extracts keyword terms from a list of queries using underlying similarity model.

        Args:
            queries: list of queries

        Returns:
            list of queries reduced down to keyword term strings
        """

        # Extract keyword terms from queries if underlying similarity model supports it
        return self.similarity.batchterms(queries) if hasattr(self.similarity, "batchterms") else queries
