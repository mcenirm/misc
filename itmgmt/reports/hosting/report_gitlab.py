from __future__ import annotations

from collections import defaultdict
from csv import DictWriter
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from sys import stdout, exit

from dataset import Database, Table, connect
from gitlab import Gitlab
from gitlab.base import RESTObject
from gitlab.const import AccessLevel
from gitlab.mixins import ListMixin
from gitlab.v4.objects.groups import Group
from gitlab.v4.objects.projects import Project
from icecream import ic
from rich import inspect as ri

__ALL__ = [
    "get_default_gitlab",
    "main",
    "report_gitlab",
]


DEFAULT_GITLAB_ID = None
DEFAULT_GITLAB_CONFIG_FILES = [str(Path("secrets", "gitlab.cfg"))]


@dataclass(kw_only=True, frozen=True)
class DbHelper:
    db: Database

    def add_item_with_attributes(
        self,
        *,
        table_name: str,
        item: RESTObject,
        key_attr: str = "id",
        ignore_attrs: set[str] = set(),
        do_not_normalize_attrs: set[str] = set(),
        list_index_key: str = "_i",
    ) -> DbHelper:
        table: Table = self.db[table_name]
        attrs = {k: v for k, v in item.attributes.items() if k not in ignore_attrs}
        item_key = attrs.pop(key_attr)
        row = {key_attr: item_key}
        for dnn_attr in do_not_normalize_attrs:
            if dnn_attr in attrs:
                dnn_value = attrs.pop(dnn_attr)
                row[dnn_attr] = dnn_value
        new_key = table.insert(row)
        assert (
            item_key == new_key
        ), f"Unexpected key mismatch for table {table_name!r}: {item_key!r} != {new_key!r}"
        property_fk_name = "_".join([table_name, key_attr])
        for k, v in attrs.items():
            property_table_name = "__".join([table_name, k])
            property_table: Table = self.db[property_table_name]
            match k, v:
                case _, str() | bool() | int() | None:
                    property_row = {property_fk_name: item_key, k: v}
                    property_table.upsert(property_row, [property_fk_name])
                case _, list():
                    property_rows = [
                        {property_fk_name: item_key, list_index_key: i, k: v}
                        for i, x in enumerate(v)
                    ]
                    property_table.upsert_many(
                        property_rows, [property_fk_name, list_index_key]
                    )
                case _, dict():
                    ic("dict", table_name, k, v)
                    exit()
                case _:
                    ic("unhandled", table_name, k, type(v))
                    exit()
        return self


def get_default_gitlab(
    *,
    gitlab_id: str | None = DEFAULT_GITLAB_ID,
    config_files: list[str] | None = DEFAULT_GITLAB_CONFIG_FILES,
) -> Gitlab:
    gl = Gitlab.from_config(gitlab_id=gitlab_id, config_files=config_files)
    gl.auth()
    return gl


def import_gitlab(gl: Gitlab, /, db_connect_url="sqlite:///:memory:") -> Database:
    db = connect(db_connect_url)
    helper = DbHelper(db=db)
    for fn, manager in [
        (import_gitlab_group, gl.groups),
        (import_gitlab_project, gl.projects),
    ]:
        manager: ListMixin = manager
        for item in islice(
            manager.list(
                iterator=True,
                min_access_level=int(AccessLevel.REPORTER),
            ),
            5,
        ):
            fn(helper, item)
    return db


def import_gitlab_group(helper: DbHelper, group: Group, /) -> DbHelper:
    helper.add_item_with_attributes(
        table_name="group",
        item=group,
        ignore_attrs={
            "avatar_url",
            "default_branch_protection",
            "emails_disabled",
            "ldap_access",
            "ldap_cn",
            "lfs_enabled",
            "mentions_disabled",
            "namespace",
            "request_access_enabled",
            "require_two_factor_authentication",
            "share_with_group_lock",
            "two_factor_grace_period",
        },
    )
    return helper


def import_gitlab_project(helper: DbHelper, project: Project, /) -> DbHelper:
    helper.add_item_with_attributes(
        table_name="project",
        item=project,
        ignore_attrs={
            "_links",
            "allow_merge_on_skipped_pipeline",
            "analytics_access_level",
            "auto_cancel_pending_pipelines",
            "auto_devops_deploy_strategy",
            "autoclose_referenced_issues",
            "avatar_url",
            "build_timeout",
            "builds_access_level",
            "can_create_merge_request_in",
            "ci_allow_fork_pipelines_to_run_in_parent_project",
            "ci_config_path",
            "ci_default_git_depth",
            "ci_forward_deployment_enabled",
            "ci_job_token_scope_enabled",
            "ci_opt_in_jwt",
            "ci_separated_caches",
            "container_expiration_policy",
            "container_registry_access_level",
            "container_registry_enabled",
            "enforce_auth_checks_on_uploads",
            "external_authorization_classification_label",
            "forking_access_level",
            "forks_count",
            "import_status",
            "issues_access_level",
            "issues_enabled",
            "jobs_enabled",
            "keep_latest_artifact",
            "lfs_enabled",
            "merge_commit_template",
            "merge_method",
            "merge_requests_access_level",
            "merge_requests_enabled",
            "namespace",
            "only_allow_merge_if_all_discussions_are_resolved",
            "only_allow_merge_if_pipeline_succeeds",
            "open_issues_count",
            "operations_access_level",
            "packages_enabled",
            "pages_access_level",
            "permissions",
            "printing_merge_request_link_enabled",
            "public_jobs",
            "readme_url",
            "remove_source_branch_after_merge",
            "repository_access_level",
            "request_access_enabled",
            "requirements_access_level",
            "requirements_enabled",
            "resolve_outdated_diff_discussions",
            "restrict_user_defined_variables",
            "runner_token_expiration_interval",
            "security_and_compliance_access_level",
            "security_and_compliance_enabled",
            "service_desk_enabled",
            "shared_runners_enabled",
            "snippets_access_level",
            "snippets_enabled",
            "squash_commit_template",
            "squash_option",
            "star_count",
            "suggestion_commit_message",
            "wiki_access_level",
            "wiki_enabled",
        },
        do_not_normalize_attrs={},
    )
    return helper


def report_gitlab(db: Database, /) -> None:
    for table_name in db.tables:
        t: Table = db[table_name]
        print("==", table_name, "==", t.count())
        w = DictWriter(stdout, t.columns)
        w.writeheader()
        for r in t:
            w.writerow(r)
        print()


def main() -> None:
    gl = get_default_gitlab()
    db = import_gitlab(gl)
    report_gitlab(db)


if __name__ == "__main__":
    main()
