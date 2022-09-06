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


DEFAULT_GITLAB_ID = None
DEFAULT_GITLAB_CONFIG_FILES = [str(Path("secrets", "gitlab.cfg"))]


ClubT = Group | Project
ClubManagerT = GroupManager | ProjectManager
ClubKeyT = Integer

MemberT = GroupMember | ProjectMember
MemberKeyT = Integer

ItemWithAttributesT = ClubT | MemberT
ItemWithAttributesKeyT = ClubKeyT | MemberKeyT
ItemWithAttributesDataT = dict[str, Any]
MemberDataT = ItemWithAttributesDataT


@dataclass(kw_only=True, frozen=True)
class TableSpecification:
    name: str
    key_name: str
    key_type: TypeEngine
    attrs_ignore: frozenset[str]
    attrs_do_not_normalize: frozenset[str]

    @property
    def name_when_used_as_foreign_key(self) -> str:
        return "_".join([self.name, self.key_name])


@dataclass(kw_only=True, frozen=True)
class PreparedItemWithAttributes:
    key: ItemWithAttributesKeyT
    attributes: ItemWithAttributesDataT
    normalize_attributes: ItemWithAttributesDataT
    extra: ItemWithAttributesDataT

    @classmethod
    def prepare_from_item_and_spec(
        cls,
        *,
        item: ItemWithAttributesT,
        spec: TableSpecification,
    ) -> PreparedItemWithAttributes:
        found_key = False
        key: ItemWithAttributesKeyT = None
        attributes: ItemWithAttributesDataT = {}
        normalize_attributes: ItemWithAttributesDataT = {}
        extra: ItemWithAttributesDataT = {}
        for k, v in item.attributes.items():
            if v is None:
                # TODO verify that omitting nulls is a good thing
                continue
            elif k == spec.key_name:
                found_key = True
                key = v
            elif k in spec.attrs_ignore:
                extra[k] = v
            elif k in spec.attrs_do_not_normalize:
                attributes[k] = v
            else:
                normalize_attributes[k] = v
        assert (
            found_key
        ), f"Expected to find key {spec.key_name!r} in {item!r} for {spec!r}"
        result = cls(
            key=key,
            attributes=attributes,
            normalize_attributes=normalize_attributes,
            extra=extra,
        )
        return result


@dataclass(kw_only=True, frozen=True)
class DbHelper:
    db: Database
    members: dict[MemberKeyT, MemberDataT] = field(default_factory=dict)

    group_table_spec: TableSpecification = TableSpecification(
        name="group",
        key_name="id",
        key_type=ClubKeyT,
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
        key_type=ClubKeyT,
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
        key_type=MemberKeyT,
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

    club_member_spec = TableSpecification(
        name="",
        key_name="",
        key_type=Any,
        attrs_ignore=frozenset(),
        attrs_do_not_normalize=frozenset(),
    )

    list_index_key: str = "_i"

    debug: defaultdict[str, dict[ItemWithAttributesKeyT, ItemWithAttributesT]] = field(
        default_factory=lambda: defaultdict(dict)
    )

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
                    primary_id=entity_spec.name_when_used_as_foreign_key,
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
        for member in self._iterate_direct_members_of_club(club):
            self._import_direct_member_of_club(
                member=member,
                club=club,
                club_spec=club_spec,
            )
        return self

    def _member_key(
        self,
        member: MemberT,
        /,
    ) -> MemberKeyT:
        k: MemberKeyT = self._item_with_attributes_key(
            member.attributes,
            self.member_table_spec,
        )
        return k

    def _item_with_attributes_key(
        self,
        item: ItemWithAttributesT,
        spec: TableSpecification,
        /,
    ) -> ItemWithAttributesKeyT:
        k: ItemWithAttributesKeyT = item.attributes[spec.key_name]
        return k

    def _iterate_direct_members_of_club(
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

    def _import_direct_member_of_club(
        self,
        member: MemberT,
        club: ClubT,
        club_spec: TableSpecification,
    ) -> DbHelper:
        prep = self._import_member(member)
        table: Table = self.db[
            "__".join(
                [
                    club_spec.name,
                    self.member_table_spec.name,
                ]
            )
        ]
        club_key = club.attributes[club_spec.key_name]
        row = {
            club_spec.name_when_used_as_foreign_key: club_key,
            self.member_table_spec.name_when_used_as_foreign_key: prep.key,
        }
        table.insert(
            row,
            [
                club_spec.name_when_used_as_foreign_key,
                self.member_table_spec.name_when_used_as_foreign_key,
            ],
        )
        return self

    def _import_member(
        self,
        member: MemberT,
        /,
    ) -> PreparedItemWithAttributes:
        expected: PreparedItemWithAttributes = (
            PreparedItemWithAttributes.prepare_from_item_and_spec(
                item=member,
                spec=self.member_table_spec,
            )
        )
        if self.has_member_data(expected.key):
            existing = self.get_member_data(expected.key)
            combined = expected.attributes | expected.normalize_attributes
            assert (
                existing == combined
            ), f"Unexpected member mismatch for key {expected.key!r}: {existing!r} != {combined!r}"
            result = expected
        else:
            actual = self._import_item_with_attributes(
                item=member,
                spec=self.member_table_spec,
            )
            self.set_member_data(
                expected.key,
                actual.attributes | actual.normalize_attributes,
            )
            result = actual
        return result

    def _import_item_with_attributes(
        self,
        *,
        item: ItemWithAttributesT,
        spec: TableSpecification,
    ) -> PreparedItemWithAttributes:
        table: Table = self.db[spec.name]
        prep = PreparedItemWithAttributes.prepare_from_item_and_spec(
            item=item,
            spec=spec,
        )
        row = {spec.key_name: prep.key} | prep.attributes
        try:
            new_key = table.insert(row)
            self.debug[spec.name][new_key] = item
            assert (
                prep.key == new_key
            ), f"Unexpected key mismatch for table {spec.name!r}: {prep.key!r} != {new_key!r}"
        except IntegrityError as ie:
            existing = self.debug[spec.name][prep.key]
            raise KeyboardInterrupt(existing, item) from ie
        property_fk_name = spec.name_when_used_as_foreign_key
        actual_properties: ItemWithAttributesDataT = {}
        for k, v in prep.normalize_attributes.items():
            property_table = self.get_property_table(spec, k)
            skip_actual = False
            match k, v:
                case _, None:
                    # avoid(?) normalized nulls
                    skip_actual = True
                case _, str() | bool() | int():
                    property_row = {property_fk_name: prep.key, k: v}
                    property_table.upsert(property_row, [property_fk_name])
                case _, list():
                    property_rows = [
                        {property_fk_name: prep.key, self.list_index_key: i, k: v}
                        for i, x in enumerate(v)
                    ]
                    property_table.upsert_many(
                        property_rows, [property_fk_name, self.list_index_key]
                    )
                case _, dict():
                    ic("dict", spec.name, prep.key, k, v)
                    exit()
                case _:
                    ic("unhandled", spec.name, prep.key, k, type(v))
                    exit()
            if not skip_actual:
                actual_properties[k] = v
        result = PreparedItemWithAttributes(
            key=prep.key,
            attributes=prep.attributes,
            normalize_attributes=actual_properties,
            extra=prep.extra,
        )
        return result


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
