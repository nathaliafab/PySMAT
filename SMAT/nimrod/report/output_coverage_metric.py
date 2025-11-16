import os
from nimrod.report.output import Output

class Output_coverage_metric(Output):

    def get_file_collumn_names(self):
        listaPartesBasicasReport = ["target_commit", "test_suite_commit", "project_name", "path_suite_base", "path_suite_merge"]
        listaCoberturaProjeto = ["pytest base: function coverage SUA", "pytest merge: function coverage SUA",
                                 "pytest base: class coverage SUA", "pytest merge: class coverage SUA",
                                 "pytest base: line coverage SUA", "pytest merge: line coverage SUA"]
        listaCoberturaClasse = ["target_class", "pytest base: function coverage CUA", "pytest merge: function coverage CUA",
                                "pytest base: line coverage CUA", "pytest merge: line coverage CUA"]
        listaCoberturaMetodo = ["target_method", "pytest base: line coverage MUA", "pytest merge: line coverage MUA",
                                "pytest base: statement coverage MUA", "pytest merge: statement coverage MUA",
                                "pytest base: branch coverage MUA", "pytest merge: branch coverage MUA"]
        listaPythonVersion = ["python_version"]

        return listaPartesBasicasReport + listaCoberturaProjeto + listaCoberturaClasse + listaCoberturaMetodo + listaPythonVersion

    def write_output_line(self, commitVersion, test_suite_commit, projectName, path_suite_base, path_suite_merge, 
                          dadosParaGravacaoBase, dadosParaGravacaoMerge, listaPartesBasicasReport,
                          listaCoberturaProjeto, listaCoberturaClasse, listaCoberturaMetodo, 
                          classeTarget, nomeMetodoTarget, python_version=None):
        if (os.path.isfile(self.output_file_path) == False):
            self.create_result_file()
        else:
            self.write_each_result(self.formate_output_line(commitVersion, test_suite_commit, projectName, path_suite_base, path_suite_merge, 
                                                          dadosParaGravacaoBase, dadosParaGravacaoMerge, listaPartesBasicasReport,
                                                          listaCoberturaProjeto, listaCoberturaClasse, listaCoberturaMetodo, 
                                                          classeTarget.replace(",","|"), nomeMetodoTarget.replace(",","|"), python_version))

    def formate_output_line(self, commitVersion, test_suite_commit, projectName, path_suite_base, path_suite_merge, 
                            dadosParaGravacaoBase, dadosParaGravacaoMerge, listaPartesBasicasReport,
                            listaCoberturaProjeto, listaCoberturaClasse, listaCoberturaMetodo, 
                            classeTarget, nomeMetodoTarget, python_version=None):
        try:
            # Check if we have target class coverage data
            if (dadosParaGravacaoBase[1][0] is True) & (dadosParaGravacaoMerge[1][0] is True):
                # Check if we have target method coverage data
                if (dadosParaGravacaoBase[2][0] is True) & (dadosParaGravacaoMerge[2][0] is True):
                    return [commitVersion, test_suite_commit, projectName, path_suite_base, path_suite_merge, 
                           dadosParaGravacaoBase[0][1], dadosParaGravacaoMerge[0][1],  # function coverage SUA
                           dadosParaGravacaoBase[0][0], dadosParaGravacaoMerge[0][0],  # class coverage SUA
                           dadosParaGravacaoBase[0][2], dadosParaGravacaoMerge[0][2],  # line coverage SUA
                           classeTarget, dadosParaGravacaoBase[1][2], dadosParaGravacaoMerge[1][2],  # target class function coverage CUA
                           dadosParaGravacaoBase[1][1], dadosParaGravacaoMerge[1][1],  # target class line coverage CUA
                           nomeMetodoTarget, dadosParaGravacaoBase[2][1], dadosParaGravacaoMerge[2][1],  # target method line coverage MUA
                           dadosParaGravacaoBase[2][2], dadosParaGravacaoMerge[2][2],  # target method statement coverage MUA
                           dadosParaGravacaoBase[2][3], dadosParaGravacaoMerge[2][3],  # target method branch coverage MUA
                           python_version]
                else:
                    # No method coverage data available
                    return [commitVersion, test_suite_commit, projectName, path_suite_base, path_suite_merge, 
                           dadosParaGravacaoBase[0][1], dadosParaGravacaoMerge[0][1],  # function coverage SUA
                           dadosParaGravacaoBase[0][0], dadosParaGravacaoMerge[0][0],  # class coverage SUA
                           dadosParaGravacaoBase[0][2], dadosParaGravacaoMerge[0][2],  # line coverage SUA
                           classeTarget, dadosParaGravacaoBase[1][2], dadosParaGravacaoMerge[1][2],  # target class function coverage CUA
                           dadosParaGravacaoBase[1][1], dadosParaGravacaoMerge[1][1],  # target class line coverage CUA
                           "", "", "", "", "", "", "",  # empty method coverage data
                           python_version]
            else:
                # No class coverage data available
                return [commitVersion, test_suite_commit, projectName, path_suite_base, path_suite_merge, 
                       dadosParaGravacaoBase[0][1], dadosParaGravacaoMerge[0][1],  # function coverage SUA
                       dadosParaGravacaoBase[0][0], dadosParaGravacaoMerge[0][0],  # class coverage SUA
                       dadosParaGravacaoBase[0][2], dadosParaGravacaoMerge[0][2],  # line coverage SUA
                       "", "", "", "", "",  # empty class coverage data
                       "", "", "", "", "", "", "",  # empty method coverage data
                       python_version]
        except Exception as e:
            print(f"Error formatting coverage output line: {e}")
        
        # Fallback with empty data
        return [commitVersion, "", projectName, "", "", "","","","","","","","","","","","","","","","","","", python_version]