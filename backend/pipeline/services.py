from cases.services import (
    CaseError as PipelineError,
    create_case as create_opportunity,
    filter_cases as filter_opportunities,
    pipeline_summary,
    stage_values,
    update_case as update_opportunity,
    update_case_stage as update_opportunity_stage,
    validate_stage,
)

__all__ = [
    "PipelineError",
    "create_opportunity",
    "filter_opportunities",
    "pipeline_summary",
    "stage_values",
    "update_opportunity",
    "update_opportunity_stage",
    "validate_stage",
]
