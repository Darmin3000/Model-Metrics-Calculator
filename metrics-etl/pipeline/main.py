from metric_extraction.unified_metric_extractor import UnifiedMetricExtractor
from alert_processing.alert_processor import AlertProcessor

from audience_transforms.executive_transform import ExecutiveTransform
from audience_transforms.model_owner_transform import ModelOwnerTransform
from audience_transforms.compliance_transform import ComplianceTransform


def run_pipeline():

    UnifiedMetricExtractor().run()

    AlertProcessor().run()

    ExecutiveTransform().run()
    ModelOwnerTransform().run()
    ComplianceTransform().run()


if __name__ == "__main__":

    run_pipeline()
