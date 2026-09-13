import os  # noqa: N999
import re

from fastapi import UploadFile

from models import ResponseSignal

from .BaseController import BaseController
from .ProjectController import ProjectController


class DataController(BaseController):
    def __init__(self):
        super().__init__()
        self.file_scale = 1048576 # Scale for converting bytes to MB

    def validate_file(self, file: UploadFile):
        # Validate file type
        if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
            return False, ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value
            
        # Validate file size
        if file.size is not None and file.size > self.app_settings.FILE_ALLOWED_SIZES_MB * self.file_scale:
            return False, ResponseSignal.FILE_SIZE_EXCEEDED.value

        return True, ResponseSignal.FILE_VALIDATED_SUCCESS.value

    def get_cleaned_filename(self, original_filename: str):
        # Remove any special characters from the filename
        cleaned_filename = re.sub(r'[^\w.]', '', original_filename.strip())
        cleaned_filename = cleaned_filename.replace(" ", "_")  # Replace spaces with underscores
        return cleaned_filename    

    def generate_unique_filepath(self, original_filename: str, project_id: str):

        random_key = self.generate_random_string(length=8)
        project_dir_path = ProjectController().get_project_path(project_id=project_id)
        cleaned_filename = self.get_cleaned_filename(original_filename)

        new_file_path = os.path.join(project_dir_path, f"{random_key}_{cleaned_filename}")
        while os.path.exists(new_file_path):
            random_key = self.generate_random_string(length=8)
            new_file_path = os.path.join(project_dir_path, f"{random_key}_{cleaned_filename}")

        return new_file_path, random_key + "_" + cleaned_filename
