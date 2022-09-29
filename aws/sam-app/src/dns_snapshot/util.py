import re

def decap_first_letter(word):
    return word[0].lower() + word[1:]

def camel_to_snake(word):
    words = re.findall('^[a-z]+|[A-Z][^A-Z]*', word)
    return '_'.join([w.lower() for w in words])

def transform_dict_key(d, transform=decap_first_letter):
    new_d = {}
    for k, v in d.items():
        if isinstance(v, dict):
            new_d[transform(k)] = transform_dict_key(v, transform=transform)
        elif isinstance(v, list):
            new_d[transform(k)] = [transform_dict_key(x, transform=transform) for x in v]
        else:
            new_d[transform(k)] = d[k]
    return new_d
    