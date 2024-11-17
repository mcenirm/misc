import gitlab


def main():
    gl = gitlab.Gitlab.from_config()
    gl.auth()

    projects = gl.projects.list(
        # all projects where I am a member
        membership=True,
        # all projects, not just first page
        iterator=True,
    )
    # TODO flag to use https remotes
    ssh_urls = [_.ssh_url_to_repo for _ in projects]

    for url in sorted(ssh_urls):
        print(url)


if __name__ == "__main__":
    main()
