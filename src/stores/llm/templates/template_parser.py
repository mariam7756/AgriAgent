import os


class TemplateParser:

    def __init__(self, language: str = None, default_language: str = "en"):
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.default_language = default_language
        self.language = None
        self.set_language(language)

    def set_language(self, language: str):
        if not language:
            self.language = self.default_language
            return
        language_path = os.path.join(self.current_path, "locales", language)
        if os.path.exists(language_path):
            self.language = language
        else:
            self.language = self.default_language

    def get(self, group: str, key: str, vars: dict = None):
        """
        لو vars فارغ — يرجع الـ Template object عشان الـ controller يعمل substitute بنفسه.
        لو vars فيه قيم — يعمل substitute هنا ويرجع string.
        """
        if not group or not key:
            return None

        group_path = os.path.join(self.current_path, "locales", self.language, f"{group}.py")
        targeted_language = self.language

        if not os.path.exists(group_path):
            group_path = os.path.join(
                self.current_path, "locales", self.default_language, f"{group}.py"
            )
            targeted_language = self.default_language

        if not os.path.exists(group_path):
            return None

        module = __import__(
            f"stores.llm.templates.locales.{targeted_language}.{group}",
            fromlist=[group],
        )
        if not module:
            return None

        key_attribute = getattr(module, key, None)
        if key_attribute is None:
            return None

        # لو مفيش vars — ارجع الـ Template object زي ما هو
        if not vars:
            return key_attribute

        # لو في vars — اعمل substitute وارجع string
        try:
            return key_attribute.substitute(vars)
        except (KeyError, ValueError):
            return str(key_attribute.template)
        