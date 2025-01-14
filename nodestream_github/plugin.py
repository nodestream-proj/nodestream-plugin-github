from nodestream.project import Project, ProjectPlugin


class GithubPlugin(ProjectPlugin):
    def activate(self, project: Project) -> None:
        project.add_plugin_scope_from_pipeline_resources(
            name="github",
            package="nodestream_github",
        )
