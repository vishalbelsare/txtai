# Segmentation

![pipeline](../../images/pipeline.png#only-light)
![pipeline](../../images/pipeline-dark.png#only-dark)

The Segmentation pipeline segments text into semantic units.

## Example

The following shows a simple example using this pipeline.

```python
from txtai.pipeline import Segmentation

# Create and run pipeline
segment = Segmentation(sentences=True)
segment("This is a test. And another test.")

# Segment text with Chonkie chunker (word, sentence, semantic, late etc)
segment = Segmentation(chunker="semantic")
segment("This is a test. And another test.")
```

The Segmentation pipeline supports segmenting `sentences`, `lines`, `paragraphs` and `sections` using a rules-based approach. Each of these modes can be set when creating the pipeline.

More advanced functionality is supported via a [Chonkie chunker](https://docs.chonkie.ai/chunkers/overview). The `chunker` keyword dynamically creates a Chonkie chunker. For example, `chunker='token'` creates a [TokenChunker](https://docs.chonkie.ai/chunkers/token-chunker), `chunker='semantic'` creates a [SemanticChunker](https://docs.chonkie.ai/chunkers/semantic-chunker) and so forth. Additional keyword arguments are passed to the chunker.

## Configuration-driven example

Pipelines are run with Python or configuration. Pipelines can be instantiated in [configuration](../../../api/configuration/#pipeline) using the lower case name of the pipeline. Configuration-driven pipelines are run with [workflows](../../../workflow/#configuration-driven-example) or the [API](../../../api#local-instance).

### config.yml
```yaml
# Create pipeline using lower case class name
segmentation:
  sentences: true

# Run pipeline with workflow
workflow:
  segment:
    tasks:
      - action: segmentation
```

### Run with Workflows

```python
from txtai import Application

# Create and run pipeline with workflow
app = Application("config.yml")
list(app.workflow("segment", ["This is a test. And another test."]))
```

### Run with API

```bash
CONFIG=config.yml uvicorn "txtai.api:app" &

curl \
  -X POST "http://localhost:8000/workflow" \
  -H "Content-Type: application/json" \
  -d '{"name":"segment", "elements":["This is a test. And another test."]}'
```

## Methods

Python documentation for the pipeline.

### ::: txtai.pipeline.Segmentation.__init__
### ::: txtai.pipeline.Segmentation.__call__
