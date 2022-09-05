from __future__ import annotations

from collections import defaultdict
from csv import DictWriter
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from sys import exit, stdout
from typing import Any, Generator

from dataset import Database, Table, connect
from gitlab import Gitlab
from gitlab.base import RESTObject
from gitlab.const import AccessLevel
from gitlab.v4.objects.groups import Group, GroupManager
from gitlab.v4.objects.members import GroupMember, ProjectMember
from gitlab.v4.objects.projects import Project, ProjectManager
from icecream import ic
from rich import inspect as ri
from sqlalchemy.exc import IntegrityError
from sqlalchemy.types import Integer, TypeEngine

__ALL__ = [
    "get_default_gitlab",
    "main",
    "report_gitlab",
]


_DEBUG = defaultdict(dict)


MemberT = GroupMember | ProjectMember
ClubT = Group | Project
ClubManagerT = GroupManager | ProjectManager
MemberKeyT = Any
MemberDataT = dict[str, Any]


DEFAULT_GITLAB_ID = None
DEFAULT_GITLAB_CONFIG_FILES = [str(Path("secrets", "gitlab.cfg"))]


@dataclass(kw_only=True, frozen=True)
class TableSpecification:
    name: str
    key_name: str
    key_type: TypeEngine
    attrs_ignore: frozenset[str]
    attrs_do_not_normalize: frozenset[str]

    @property
    def foreign_key_name(self) -> str:
        return "_".join([self.name, self.key_name])


@dataclass(kw_only=True, frozen=True)
class DbHelper:
    db: Database
    members: dict[MemberKeyT, MemberDataT] = field(default_factory=dict)

    group_table_spec: TableSpecification = TableSpecification(
        name="group",
        key_name="id",
        key_type=Integer,
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
        attrs_do_not_normalize=frozenset(
            {
                "created_at",
                "description",
                "full_name",
                "full_path",
                "name",
                # "parent_id",
                "path",
                "project_creation_level",
                "subgroup_creation_level",
                "visibility",
                "web_url",
            }
        ),
    )

    project_table_spec: TableSpecification = TableSpecification(
        name="project",
        key_name="id",
        key_type=Integer,
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
        attrs_do_not_normalize=frozenset(
            {
                "archived",
                "auto_devops_enabled",
                "container_registry_image_prefix",
                "created_at",
                "creator_id",
                "default_branch",
                "description",
                "empty_repo",
                "http_url_to_repo",
                "last_activity_at",
                "name",
                "name_with_namespace",
                "path",
                "path_with_namespace",
                "service_desk_address",
                "ssh_url_to_repo",
                "visibility",
                "web_url",
            }
        ),
    )

    member_table_spec = TableSpecification(
        name="member",
        key_name="id",
        key_type=Integer,
        attrs_ignore=frozenset(
            {
                "access_level",
                "created_at",
                "created_by",
                "expires_at",
                "group_id",
                "membership_state",
            }
        ),
        attrs_do_not_normalize=frozenset(
            {
                "avatar_url",
                "name",
                "state",
                "username",
                "web_url",
            }
        ),
    )

    list_index_key: str = "_i"

    def has_member_data(
        self,
        member_key: MemberKeyT,
        /,
    ) -> bool:
        return member_key in self.members

    def get_member_data(
        self,
        member_key: MemberKeyT,
        /,
    ) -> MemberDataT:
        return self.members.get(member_key)

    def set_member_data(
        self,
        member_key: MemberKeyT,
        member_data: MemberDataT,
        /,
    ) -> None:
        self.members[member_key] = member_data

    def import_groups(self, manager: GroupManager, /) -> DbHelper:
        for group in self._iterate_clubs(manager):
            self.import_group(group)
        return self

    def import_projects(self, manager: ProjectManager, /) -> DbHelper:
        for project in self._iterate_clubs(manager):
            self.import_project(project)
        return self

    def get_property_table(
        self,
        entity_spec: TableSpecification,
        property_name: str,
        /,
        *,
        entity_fk_is_primary_key: bool = True,
    ) -> Table:
        property_table_name = "__".join([entity_spec.name, property_name])
        table_needs_init = property_table_name not in self.db
        if table_needs_init:
            table_init_kwargs = (
                dict(
                    primary_id=entity_spec.foreign_key_name,
                    primary_type=entity_spec.key_type,
                    primary_increment=None,
                )
                if entity_fk_is_primary_key
                else {}
            )
            property_table = self.db.create_table(
                property_table_name,
                **table_init_kwargs,
            )
        else:
            property_table: Table = self.db[property_table_name]
        return property_table

    def _iterate_clubs(
        self,
        manager: ClubManagerT,
        /,
        *,
        min_access_level: AccessLevel = AccessLevel.REPORTER,
    ) -> Generator[ClubT, None, None]:
        # TODO remove islice
        for club in islice(
            manager.list(
                iterator=True,
                min_access_level=int(min_access_level),
            ),
            5,
        ):
            yield club

    def import_group(self, group: Group, /) -> DbHelper:
        return self._import_club(
            club=group,
            club_spec=self.group_table_spec,
        )

    def import_project(self, project: Project, /) -> DbHelper:
        return self._import_club(
            club=project,
            club_spec=self.project_table_spec,
        )

    def _import_club(
        self,
        *,
        club: ClubT,
        club_spec: TableSpecification,
    ) -> DbHelper:
        self._import_item_with_attributes(
            item=club,
            spec=club_spec,
        )
        for member in self._iterate_direct_members(club):
            self._import_direct_member(
                member=member,
                club=club,
                club_spec=club_spec,
            )
        return self

    def _member_key(self, member: MemberT, /) -> str:
        return member.attributes[self.member_table_spec.key_name]

    def _import_item_with_attributes(
        self,
        *,
        item: RESTObject,
        spec: TableSpecification,
    ) -> DbHelper:
        table: Table = self.db[spec.name]
        attrs = {k: v for k, v in item.attributes.items() if k not in spec.attrs_ignore}
        item_key = attrs.pop(spec.key_name)
        row = {spec.key_name: item_key}
        for dnn_attr in spec.attrs_do_not_normalize:
            if dnn_attr in attrs:
                dnn_value = attrs.pop(dnn_attr)
                row[dnn_attr] = dnn_value
        try:
            new_key = table.insert(row)
            _DEBUG[spec.name][new_key] = item
            assert (
                item_key == new_key
            ), f"Unexpected key mismatch for table {spec.name!r}: {item_key!r} != {new_key!r}"
        except IntegrityError as ie:
            existing = _DEBUG[spec.name][item_key]
            raise KeyboardInterrupt(existing, item) from ie
        property_fk_name = spec.foreign_key_name
        for k, v in attrs.items():
            property_table = self.get_property_table(spec, k)
            match k, v:
                case _, None:
                    # avoid(?) normalized nulls
                    ...
                case _, str() | bool() | int():
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
                    ic("dict", spec.name, item_key, k, v)
                    exit()
                case _:
                    ic("unhandled", spec.name, item_key, k, type(v))
                    exit()
        return self

    def _iterate_direct_members(
        self,
        club: ClubT,
        /,
    ) -> Generator[MemberT, None, None]:
        # TODO remove islice
        for member in islice(
            club.members.list(iterator=True),
            3,
        ):
            yield member

    def _import_direct_member(
        self,
        member: MemberT,
        club: ClubT,
        club_spec: TableSpecification,
    ) -> DbHelper:
        member_key = self._member_key(member)
        member_data = self._member_as_member_data(member)
        if self.has_member_data(member_key):
            existing_member_data = self.get_member_data(member_key)
            assert (
                existing_member_data == member_data
            ), f"Unexpected member mismatch: {existing_member_data} != {member_data}"
        else:
            self.set_member_data(member_key, member_data)
            self._import_item_with_attributes(item=member, spec=self.member_table_spec)
        table: Table = self.db[
            "__".join(
                [
                    club_spec.name,
                    self.member_table_spec.name,
                ]
            )
        ]
        club_key = club.attributes[club_spec.key_name]
        table.insert(
            {
                club_spec.foreign_key_name: club_key,
                self.member_table_spec.foreign_key_name: member_key,
            },
            [
                club_spec.foreign_key_name,
                self.member_table_spec.foreign_key_name,
            ],
        )
        return self

    def _member_as_member_data(self, member: MemberT, /) -> MemberDataT:
        return {
            k: v
            for k, v in member.attributes.items()
            if k not in self.member_table_spec.attrs_ignore
        }


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
    try:
        helper.import_groups(gl.groups)
        helper.import_projects(gl.projects)
    except KeyboardInterrupt as ki:
        for a in ki.args:
            ri(a)
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
