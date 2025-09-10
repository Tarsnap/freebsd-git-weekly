import dataclasses
import importlib.resources
import tomllib


@dataclasses.dataclass
class HtmlTemplates:
    def __post_init__(self):
        data_path = importlib.resources.files("commits_periodical").joinpath(
            "html_templates.toml"
        )
        with data_path.open("rb") as fp:
            self.doc = tomllib.load(fp)

        # Promote all those templates to object attributes
        for key, value in self.doc.items():
            setattr(self, key, value)

    # FIXME: this was only added to stop pylint complaining about E1101;
    # there must be a better way of handling it.
    def __getattr__(self, item):
        raise AttributeError(f"{item} not found")
