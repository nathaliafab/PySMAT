from collections import namedtuple


Mutant = namedtuple('Mutant', [
    'mid', 
    'operator',
    'line_number',
    'method',
    'transformation',
    'dir'
]) 
