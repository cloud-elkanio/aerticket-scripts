import ast

with open('tools/roles_and_permision/roles/all_roles.py', 'r') as file:
    lines = file.readlines()
    

for i, line in enumerate(lines):
    if line.startswith('a = '):
        dict_type = line.split('=')[1].strip()
        deval = ast.literal_eval(dict_type)
        deval.append('hellothisis my code')
        updated_dict_str = f'a = {deval}\n'
        lines[i] = updated_dict_str
    




with open('tools/roles_and_permision/roles/all_roles.py', 'w') as file:
    file.writelines(lines)