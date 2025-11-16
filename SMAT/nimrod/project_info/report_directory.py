import os
import shutil
from distutils.dir_util import copy_tree

class ReportDirectory:

    def __init__(self, directory_path):
        self.main_directory_path = directory_path
        self.report_directory_path = self.create_report_directory()

    def create_report_directory(self):
        os.chdir(self.main_directory_path)
        teste = os.getcwd()
        try:
            if not os.path.exists(os.path.join(self.main_directory_path,"database")):
                os.mkdir("database")
                os.chdir("database")
            else:
                os.chdir("database")
        except:
            os.chdir("database")
        teste = os.getcwd()
        return os.getcwd()

    def create_directory_to_project(self, project_name):
        os.chdir(self.report_directory_path)
        try:
            if not os.path.exists(os.path.join(self.report_directory_path,project_name)):
                os.mkdir(project_name)
                return True
        except OSError:
            print ("Error: creating directory. "+project_name)
        return False

    def save_compiled_project_version(self, project_name, compiled_version_path, merge_scenario, hash):
        os.chdir (self.report_directory_path)
        try:
            if os.path.exists(os.chdir(project_name)):
                os.chdir(project_name)
        except:
            self.create_directory_to_project(project_name)

        try:
            if os.path.exists(os.path.join(project_name,merge_scenario)):
                os.chdir(os.path.join(project_name,merge_scenario))
            else:
                self.create_directory_for_merge_scenario(merge_scenario, project_name)
                os.chdir(merge_scenario)
        except:
            os.chdir(merge_scenario)

        try:
            os.mkdir(hash)
            os.chdir(hash)
            path_hash = os.getcwd()
            copy_tree(compiled_version_path, path_hash)
        except OSError:
            print ("It was not possible to save the commit directories here. It already exists or another problem has happened.")

    def create_directory_for_merge_scenario(self, hash, project_name):
        os.chdir(os.path.join(self.report_directory_path,project_name))
        os.mkdir(hash)

    def remove_failed_merge_scenario(self, project_name, merge_scenario):
        try:
            if os.path.exists(os.path.join(self.report_directory_path, project_name, merge_scenario)):
                shutil.rmtree(os.path.join(self.report_directory_path,project_name,merge_scenario))
            else:
                print ("No directory named "+self.report_directory_path+"/"+project_name+"/"+merge_scenario+" was found.")
        except OSError:
            print ("Error: removing directory. "+self.report_directory_path+"/"+project_name+"/"+merge_scenario)

    def get_compiled_version_path_for_commit(self, project_name, merge_scenario, hash):
        try:
            if os.path.exists(os.path.join(self.report_directory_path,project_name,merge_scenario,hash)):
                os.chdir(os.path.join(self.report_directory_path,project_name,merge_scenario,hash))
                return os.getcwd()
        except OSError:
            print ("There is no directory for the commit "+hash+".")
            return ""