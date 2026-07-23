"""
Technique recognition schemas (separate from EWSD density prediction).

Classifier confidence scores and ranks are not converted to EWSD coefficients.
"""

from string_technique_model.recognition.models import (
    RecognitionLabelMapping,
    RecognitionLabelMappingRegistry,
    TechniqueRecognitionResult,
)
from string_technique_model.recognition.registry import (
    get_recognition_label_mapping,
    load_recognition_label_mappings,
)

__all__ = [
    "RecognitionLabelMapping",
    "RecognitionLabelMappingRegistry",
    "TechniqueRecognitionResult",
    "get_recognition_label_mapping",
    "load_recognition_label_mappings",
]
