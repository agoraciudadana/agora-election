#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import sys
import json
import re
import requests

def file_to_dict(fpath):
    '''
    converts a TSV file with a header line with column names to a list of dicts
    '''
    with open(fpath, 'r', encoding="utf-8") as f:
        data = f.read()

    lines = data.split('\n')
    keynames = []
    ret = []

    # first line specifies the columns
    first = True
    for line in lines:
        line = line.strip()
        if first:
            keynames = line.split('\t')
            first = False
            continue

        pairs = [(key, value) for key, value in zip(keynames, line.split('\t'))]
        ret.append(dict(pairs))

    return ret

def get_details(cand):
    '''
    Obtains the candidate detailed description
    '''
    headline = [cand.get('Profesión', ''),
                cand.get('Edad', ''),
                cand.get('Ciudad', ''),]
    headline = [el for el in headline if el != '']
    return '<p>%s.</p> <p>%s</p>' % (
        ', '.join(headline),
        cand.get('Texto presentación', '').replace('   ', '</p><p>')\
            .replace('.  ', '</p><p>'))

def get_first_url(s, secure=False):
    '''
    Gets only one url
    '''
    ret = "http" + s.strip().split('http')[1].strip()
    if secure:
        ret.replace("http://", "https://")
    return ret

def get_urls(cand):
    '''
    Obtains the urls given the candidate data
    '''
    ret = []
    if cand.get('Facebook', '').strip().startswith("http"):
        ret.append(dict(
            title="Facebook",
            url=get_first_url(cand['Facebook'], True))
        )
    if cand.get('Twitter', '').strip().startswith("http"):
        ret.append(dict(
            title="Twitter",
            url=get_first_url(cand['Twitter'], True))
        )
    if cand.get('Web/Blog', '').strip().startswith("http"):
        ret.append(dict(
            title="Web",
            url=get_first_url(cand['Web/Blog']))
        )
    if cand.get('Vídeo', '').strip().startswith("http"):
        ret.append(dict(
            title="Youtube",
            url=get_first_url(cand['Vídeo'], True))
        )
    return ret

def get_media_url(cand):
    return cand.get('Link foto', '').replace(
        'http://www.podemos.info/sites/default/files/',
        'https://primarias.podemos.info/static2/cands/')

def main():
    '''
    Executes the main task
    '''
    data = file_to_dict(sys.argv[1])

    # iterate through the candidates
    ret = []
    for cand in data:
        cand_data = dict(
            a="ballot/answer",
            value=cand['Nombre'],
            details=get_details(cand),
            details_title="Presentación y motivos",
            media_url=get_media_url(cand),
            urls=get_urls(cand)
        )
        ret.append(cand_data)

    # TODO: sort by a specified column

    print(json.dumps(ret, indent=4))

if __name__ == "__main__":
    main()
