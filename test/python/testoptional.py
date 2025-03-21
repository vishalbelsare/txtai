"""
Optional module tests
"""

import sys
import unittest

# pylint: disable=C0415,W0611
import transformers
from transformers import Trainer, set_seed, ViTFeatureExtractor


class TestOptional(unittest.TestCase):
    """
    Optional tests. Simulates optional dependencies not being installed.
    """

    @classmethod
    def setUpClass(cls):
        """
        Simulate optional packages not being installed
        """

        modules = [
            "annoy",
            "croniter",
            "fastapi",
            "fasttext",
            "hnswlib",
            "imagehash",
            "nltk",
            "libcloud.storage.providers",
            "onnxmltools",
            "onnxruntime",
            "pandas",
            "PIL",
            "sklearn.decomposition",
            "sentence_transformers",
            "soundfile",
            "tika",
            "xmltodict",
        ]

        # Get handle to all currently loaded txtai modules
        modules = modules + [key for key in sys.modules if key.startswith("txtai")]
        cls.modules = {module: None for module in modules}

        # Replace loaded modules with stubs. Save modules for later reloading
        for module in cls.modules:
            if module in sys.modules:
                cls.modules[module] = sys.modules[module]

            # Remove txtai modules. Set optional dependencies to None to prevent reloading.
            if "txtai" in module:
                if module in sys.modules:
                    del sys.modules[module]
            else:
                sys.modules[module] = None

    @classmethod
    def tearDownClass(cls):
        """
        Resets modules environment back to initial state.
        """

        # Reset replaced modules in setup
        for key, value in cls.modules.items():
            if value:
                sys.modules[key] = value
            else:
                del sys.modules[key]

    def testApi(self):
        """
        Test missing api dependencies
        """

        with self.assertRaises(ImportError):
            import txtai.api

    def testCloud(self):
        """
        Test missing cloud dependencies
        """

        from txtai.embeddings import Cloud

        with self.assertRaises(ImportError):
            Cloud(None)

    def testDatabase(self):
        """
        Test missing database dependencies
        """

        from txtai.database import ImageEncoder

        with self.assertRaises(ImportError):
            ImageEncoder()

    def testModel(self):
        """
        Test missing model dependencies
        """

        from txtai.embeddings import Reducer
        from txtai.models import OnnxModel

        with self.assertRaises(ImportError):
            Reducer()

        with self.assertRaises(ImportError):
            OnnxModel(None)

    def testPipeline(self):
        """
        Test missing pipeline dependencies
        """

        from txtai.pipeline import Caption, HFOnnx, ImageHash, MLOnnx, Objects, Segmentation, Tabular, Textractor, Transcription, Translation

        with self.assertRaises(ImportError):
            Caption()

        with self.assertRaises(ImportError):
            HFOnnx()("google/bert_uncased_L-2_H-128_A-2", quantize=True)

        with self.assertRaises(ImportError):
            ImageHash()

        with self.assertRaises(ImportError):
            MLOnnx()

        with self.assertRaises(ImportError):
            Objects()

        with self.assertRaises(ImportError):
            Segmentation()

        with self.assertRaises(ImportError):
            Tabular()

        with self.assertRaises(ImportError):
            Textractor()

        with self.assertRaises(ImportError):
            Transcription()

        with self.assertRaises(ImportError):
            Translation().detect(["test"])

    def testSimilarity(self):
        """
        Test missing similarity dependencies
        """

        from txtai.ann import ANNFactory
        from txtai.vectors import VectorsFactory

        with self.assertRaises(ImportError):
            ANNFactory.create({"backend": "annoy"})

        with self.assertRaises(ImportError):
            ANNFactory.create({"backend": "hnsw"})

        with self.assertRaises(ImportError):
            VectorsFactory.create({"method": "words"}, None)

        with self.assertRaises(ImportError):
            VectorsFactory.create({"method": "sentence-transformers", "path": ""}, None)

    def testWorkflow(self):
        """
        Test missing workflow dependencies
        """

        from txtai.workflow import ExportTask, ImageTask, ServiceTask, StorageTask, Workflow

        with self.assertRaises(ImportError):
            ExportTask()

        with self.assertRaises(ImportError):
            ImageTask()

        with self.assertRaises(ImportError):
            ServiceTask()

        with self.assertRaises(ImportError):
            StorageTask()

        with self.assertRaises(ImportError):
            Workflow([], workers=1).schedule(None, [])
