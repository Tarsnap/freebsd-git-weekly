import importlib.resources
import string
import tomllib


class HtmlTemplates:
    INDEX: string.Template
    HTML_BEGIN: string.Template
    INTRO_SECTION: string.Template
    INTRO_DEBUG_MESSAGE: string.Template
    TECHNICAL_NOTES_SECTION: string.Template
    HTML_SECTION: string.Template
    HTML_COMMIT_TAGLINE: string.Template
    HTML_DETAILS_OUTER: string.Template
    HTML_DETAILS_INNER: string.Template
    HTML_END: string.Template
    RELEASE_DEBUG: string.Template
    TEXT_ANNOUNCEMENT: string.Template
    TEXT_HIGHLIGHTED: string.Template

    def __init__(self) -> None:
        data_path = importlib.resources.files("commits_periodical").joinpath(
            "html_templates.toml"
        )
        with data_path.open("rb") as fp:
            doc = tomllib.load(fp)

        # Promote all those templates to object attributes
        for key, value in doc.items():
            setattr(self, key, string.Template(value))

        missing = set(self.__annotations__) - set(doc)
        if missing:
            raise ValueError(f"Missing templates in toml: {missing}")
