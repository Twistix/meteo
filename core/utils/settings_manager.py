import json
import os

class SettingsManager:
    def __init__(self, model_settings_path, user_settings_path):
        """
        Initialize the settings manager with paths to the settings files.
        :param model_settings_path: Path to the model settings JSON file.
        :param user_settings_path: Path to the user settings JSON file.
        """
        self.model_settings_path = model_settings_path
        self.user_settings_path = user_settings_path

        # Load settings during initialization
        self.model_settings = self._load_settings(self.model_settings_path, "model")
        self.user_settings = self._load_settings(self.user_settings_path, "user")

    def _load_settings(self, path, settings_type):
        """
        Load and validate a JSON settings file.
        :param path: Path to the JSON file.
        :param settings_type: Type of settings being loaded ("model" or "user").
        :return: Parsed JSON content as a dictionary.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"{settings_type.capitalize()} settings file not found: {path}")
        
        with open(path, "r") as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Error parsing {settings_type} settings file: {e}")
        
        return settings

    def get_model_settings(self):
        """
        Get the loaded model settings.
        :return: Dictionary containing the model settings.
        """
        return self.model_settings

    def get_user_settings(self):
        """
        Get the loaded user settings.
        :return: Dictionary containing the user settings.
        """
        return self.user_settings
