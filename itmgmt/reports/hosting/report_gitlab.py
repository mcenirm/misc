from __future__ import annotations

from csv import DictWriter
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from sys import exit, stdout
from typing import Generator

from dataset import Database, Table, connect
from gitlab import Gitlab
from gitlab.base import RESTObject
from gitlab.const import AccessLevel
from gitlab.v4.objects.groups import Group, GroupManager
from gitlab.v4.objects.members import GroupMember, ProjectMember
from gitlab.v4.objects.projects import Project, ProjectManager
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
class TableSpecification:
    name: str
    attr_key: str
    attrs_ignore: frozenset[str]
    attrs_do_not_normalize: frozenset[str]


@dataclass(kw_only=True, frozen=True)
class DbHelper:
    db: Database

    group_table_spec: TableSpecification = TableSpecification(
        name="group",
        attr_key="id",
        attrs_ignore=frozenset(
            {
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
            }
        ),
        attrs_do_not_normalize=frozenset(),
    )

    project_table_spec: TableSpecification = TableSpecification(
        name="project",
        attr_key="id",
        attrs_ignore=frozenset(
            {
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
            }
        ),
        attrs_do_not_normalize=frozenset(),
    )

    list_index_key: str = "_i"

    def import_groups(self, manager: GroupManager, /) -> DbHelper:
        for group in self._iterate_groups_or_projects(manager):
            self.import_group(group)
        return self

    def import_projects(self, manager: ProjectManager, /) -> DbHelper:
        for project in self._iterate_groups_or_projects(manager):
            self.import_project(project)
        return self

    def _iterate_groups_or_projects(
        self,
        manager: GroupManager | ProjectManager,
        /,
        *,
        min_access_level: AccessLevel = AccessLevel.REPORTER,
    ) -> Generator[Group | Project, None, None]:
        # TODO remove islice
        for group_or_project in islice(
            manager.list(
                iterator=True,
                min_access_level=int(min_access_level),
            ),
            5,
        ):
            yield group_or_project

    def import_group(self, group: Group, /) -> DbHelper:
        self._import_item_with_attributes(
            item=group,
            spec=self.group_table_spec,
        )
        # for member in self._iterate_direct_members(group):
        #     self._import_direct_member()
        #     ri(member)
        #     exit()
        return self

    def import_project(self, project: Project, /) -> DbHelper:
        self._import_item_with_attributes(
            item=project,
            spec=self.project_table_spec,
        )
        return self

    def _import_item_with_attributes(
        self,
        *,
        item: RESTObject,
        spec: TableSpecification,
    ) -> DbHelper:
        table: Table = self.db[spec.name]
        attrs = {k: v for k, v in item.attributes.items() if k not in spec.attrs_ignore}
        item_key = attrs.pop(spec.attr_key)
        row = {spec.attr_key: item_key}
        for dnn_attr in spec.attrs_do_not_normalize:
            if dnn_attr in attrs:
                dnn_value = attrs.pop(dnn_attr)
                row[dnn_attr] = dnn_value
        new_key = table.insert(row)
        assert (
            item_key == new_key
        ), f"Unexpected key mismatch for table {spec.name!r}: {item_key!r} != {new_key!r}"
        property_fk_name = "_".join([spec.name, spec.attr_key])
        for k, v in attrs.items():
            property_table_name = "__".join([spec.name, k])
            property_table: Table = self.db[property_table_name]
            match k, v:
                case _, str() | bool() | int() | None:
                    property_row = {property_fk_name: item_key, k: v}
                    property_table.upsert(property_row, [property_fk_name])
                case _, list():
                    property_rows = [
                        {property_fk_name: item_key, self.list_index_key: i, k: v}
                        for i, x in enumerate(v)
                    ]
                    property_table.upsert_many(
                        property_rows, [property_fk_name, self.list_index_key]
                    )
                case _, dict():
                    ic("dict", spec.name, k, v)
                    exit()
                case _:
                    ic("unhandled", spec.name, k, type(v))
                    exit()
        return self

    def _iterate_direct_members(
        self,
        group_or_project: Group | Project,
        /,
    ) -> Generator[GroupMember | ProjectMember, None, None]:
        # TODO remove islice
        for member in islice(
            group_or_project.members.list(iterator=True),
            3,
        ):
            yield member


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
    helper.import_groups(gl.groups)
    helper.import_projects(gl.projects)
    return db


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
