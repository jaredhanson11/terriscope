"""Routers package."""

from .auth import auth_router
from .auth_sso import sso_router
from .building_baselines import building_baselines_router
from .building_export import building_export_router
from .building_interventions import building_interventions_router
from .building_performance_standards import building_performance_standards_router
from .building_results import building_results_router
from .building_roles import building_roles_router
from .building_tags import building_tags_router
from .buildings import buildings_router
from .buildings_emission_factors import building_emission_factors_router
from .buildings_financials import building_financials_router
from .buildings_misc import buildings_misc_router
from .buildings_upload import buildings_upload
from .common import common_router
from .config import config_router
from .dashboards import dashboards_router
from .docs import docs_router
from .interventions import intervention_router
from .me import me_router
from .model_refinement_presets import model_refinement_presets_router
from .performance_standards import performance_standards_router
from .teams import teams_router
from .uploads import uploads_router

__all__ = [
    "auth_router",
    "building_baselines_router",
    "building_emission_factors_router",
    "building_export_router",
    "building_financials_router",
    "building_interventions_router",
    "building_performance_standards_router",
    "building_results_router",
    "building_roles_router",
    "building_tags_router",
    "buildings_misc_router",
    "buildings_router",
    "buildings_upload",
    "common_router",
    "config_router",
    "dashboards_router",
    "docs_router",
    "intervention_router",
    "me_router",
    "model_refinement_presets_router",
    "performance_standards_router",
    "sso_router",
    "teams_router",
    "uploads_router",
]
