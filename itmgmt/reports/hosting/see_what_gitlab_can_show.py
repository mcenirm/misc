from __future__ import annotations

from enum import Enum, auto
from sys import stderr

from gitlab import Gitlab
from icecream import ic
from rich import inspect as ri

from report_gitlab import get_default_gitlab

__ALL__ = ["main", "see_what_gitlab_can_show"]


class TopicCategory(Enum):
    avoid = auto()
    dive = auto()
    ignore = auto()
    include = auto()
    template = auto()
    todo = auto()
    uncertain = auto()


GITLAB_API_TOPICS = dict(
    appearance=TopicCategory.uncertain,
    applications=TopicCategory.avoid,
    audit_events=TopicCategory.avoid,
    broadcastmessages=TopicCategory.ignore,
    ci_lint=TopicCategory.uncertain,
    deploykeys=TopicCategory.avoid,
    deploytokens=TopicCategory.avoid,
    dockerfiles=TopicCategory.template,
    events=TopicCategory.ignore,
    features=TopicCategory.avoid,
    geonodes=TopicCategory.avoid,
    gitignores=TopicCategory.template,
    gitlabciymls=TopicCategory.template,
    groups=TopicCategory.dive,
    hooks=TopicCategory.avoid,
    issues_statistics=TopicCategory.uncertain,
    issues=TopicCategory.todo,
    keys=TopicCategory.uncertain,
    ldapgroups=TopicCategory.uncertain,
    licenses=TopicCategory.template,
    mergerequests=TopicCategory.todo,
    namespaces=TopicCategory.uncertain,
    notificationsettings=TopicCategory.uncertain,
    pagesdomains=TopicCategory.avoid,
    personal_access_tokens=TopicCategory.ignore,
    projects=TopicCategory.dive,
    registry_repositories=TopicCategory.uncertain,
    runners_all=TopicCategory.avoid,
    runners=TopicCategory.ignore,
    settings=TopicCategory.uncertain,
    sidekiq=TopicCategory.uncertain,
    snippets=TopicCategory.ignore,
    todos=TopicCategory.ignore,
    topics=TopicCategory.ignore,
    user_activities=TopicCategory.avoid,
    users=TopicCategory.ignore,
    variables=TopicCategory.avoid,
)


def see_what_gitlab_can_show(gl: Gitlab, /) -> None:
    from gitlab.const import AccessLevel
    from gitlab.exceptions import GitlabListError
    from gitlab.mixins import ListMixin
    from gitlab.v4.objects.groups import Group, GroupManager
    from gitlab.v4.objects.projects import Project, ProjectManager

    # user = gl.user
    for attr_name, what_to_do in GITLAB_API_TOPICS.items():
        if what_to_do != TopicCategory.dive:
            continue
        manager = getattr(gl, attr_name)
        match manager:
            case GroupManager():
                groups = manager.list(
                    iterator=True,
                    min_access_level=int(AccessLevel.REPORTER),
                )
                ic(groups.total)
                for i, group in enumerate(groups):
                    group: Group = group
                    group_url = group.attributes["web_url"]
                    print(i, group_url, file=stderr)
            case ProjectManager():
                projects = manager.list(
                    iterator=True,
                    min_access_level=int(AccessLevel.REPORTER),
                )
                ic(projects.total)
                for i, project in enumerate(projects):
                    project: Project = project
                    project_url = project.attributes["web_url"]
                    print(i, project_url, file=stderr)
            case ListMixin():
                try:
                    items = manager.list(iterator=True)
                    ic(attr_name, items.total)
                    first_item = next(items, None)
                    if first_item is None:
                        ic("missing", attr_name)
                    else:
                        ri(first_item)
                    break
                except GitlabListError as le:
                    ic("avoid", attr_name, le)
                    break
            case _:
                print(
                    "unhandled",
                    what_to_do.name,
                    repr(attr_name),
                    type(manager).__name__,
                    file=stderr,
                )


def main() -> None:
    see_what_gitlab_can_show(get_default_gitlab())


if __name__ == "__main__":
    main()
