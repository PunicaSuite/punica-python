#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json

from os import listdir, getcwd, path

from click import echo
import requests

from halo import Halo
from git import RemoteProgress, Repo, GitCommandError

from punica.utils.file_system import (
    ensure_remove_dir_if_exists,
    remove_file_if_exists,
    ensure_path_exists
)

from punica.exception.punica_exception import PunicaError, PunicaException


class Box:
    @staticmethod
    def handle_ignorance(repo_to_path: str = '') -> bool:
        unpack_spinner = Halo(text="Unpacking...", spinner='dots')
        unpack_spinner.start()
        box_ignore_file_path = path.join(repo_to_path, 'punica-box.json')
        try:
            with open(box_ignore_file_path, 'r') as f:
                box_ignore_files = json.load(f)['ignore']
            remove_file_if_exists(box_ignore_file_path)
        except FileNotFoundError:
            unpack_spinner.fail()
            return False
        for file in box_ignore_files:
            try:
                file_path = path.join(repo_to_path, file)
                ensure_remove_dir_if_exists(file_path)
                remove_file_if_exists(file_path)
            except (PermissionError, FileNotFoundError):
                unpack_spinner.fail()
                return False
        unpack_spinner.succeed()
        return True

    @staticmethod
    def prepare_download(box_name: str, to_path: str = '') -> bool:
        prepare_spinner = Halo(text="Preparing to download", spinner='dots')
        prepare_spinner.start()
        if to_path == '':
            to_path = getcwd()
        ensure_path_exists(to_path)
        if listdir(to_path):
            echo('This directory is non-empty...')
            prepare_spinner.fail()
            return False
        repo_url = Box.generate_repo_url(box_name)
        if requests.get(repo_url).status_code != 200:
            echo('Please check the box name you input.')
            prepare_spinner.fail()
            return False
        prepare_spinner.succeed()
        return True

    @staticmethod
    def init(to_path: str):
        if not Box.prepare_download(to_path):
            return
        repo_url = 'https://github.com/punica-box/punica-init-default-box'
        if Box.download_repo(repo_url, to_path):
            Box.handle_ignorance(to_path)
            echo('Unbox successful. Sweet!')
            Box.echo_box_help_cmd()
        else:
            echo('Unbox successful. Enjoy it!')

    @staticmethod
    def unbox(box_name: str, to_path: str = '') -> bool:
        prepare_spinner = Halo(text="Preparing to download", spinner='dots')
        prepare_spinner.start()
        ensure_path_exists(to_path)
        if listdir(to_path):
            echo('This directory is non-empty...')
            prepare_spinner.fail()
            return False
        repo_url = Box.generate_repo_url(box_name)
        if requests.get(repo_url).status_code != 200:
            echo(f"Punica Box {box_name} doesn't exist.")
            prepare_spinner.fail()
            return False
        prepare_spinner.succeed()
        if Box.download_repo(repo_url, to_path):
            Box.handle_ignorance(to_path)
            echo('Unbox successful. Sweet!')
            Box.echo_box_help_cmd()
            return True
        echo('Unbox failed. Sorry.')
        return False

    @staticmethod
    def generate_repo_url(box_name: str) -> str:
        if re.match(r'^([a-zA-Z0-9-])+$', box_name):
            repo_url = ['https://github.com/punica-box/', box_name, '-box', '.git']
        elif re.match(r'^([a-zA-Z0-9-])+/([a-zA-Z0-9-])+$', box_name) is None:
            repo_url = ['https://github.com/', box_name, '.git']
        else:
            raise PunicaException(PunicaError.invalid_box_name)
        return ''.join(repo_url)

    @staticmethod
    def download_repo(repo_url: str, repo_to_path: str = ''):
        if repo_to_path == '':
            repo_to_path = getcwd()
        receiving_spinner = Halo(spinner='dots')
        resolving_spinner = Halo(spinner='dots')
        counting_spinner = Halo(spinner='dots')
        compressing_spinner = Halo(spinner='dots')

        spinners = [receiving_spinner, resolving_spinner, counting_spinner, compressing_spinner]

        def update(self, op_code, cur_count, max_count=None, message=''):
            if op_code == RemoteProgress.COUNTING:
                if counting_spinner.spinner_id is None:
                    counting_spinner.start()
                scale = round(cur_count / max_count * 100, 2)
                counting_spinner.text = f'Counting objects: {scale}% ({cur_count}/{max_count})'
                if scale == 100:
                    counting_spinner.succeed()
            if op_code == RemoteProgress.COMPRESSING:
                if compressing_spinner.spinner_id is None:
                    compressing_spinner.start()
                scale = round(cur_count / max_count * 100, 2)
                compressing_spinner.text = f'Compressing objects: {scale}% ({cur_count}/{max_count})'
                if scale == 100:
                    compressing_spinner.succeed()
            if op_code == RemoteProgress.RECEIVING:
                if receiving_spinner.spinner_id is None:
                    receiving_spinner.start()
                scale = round(cur_count / max_count * 100, 2)
                receiving_spinner.text = f'Receiving objects: {scale}%, {message}'
                if scale == 100:
                    receiving_spinner.succeed()
            if op_code == RemoteProgress.RESOLVING:
                if resolving_spinner.spinner_id is None:
                    resolving_spinner.start()
                scale = round(cur_count / max_count * 100, 2)
                resolving_spinner.text = f'Resolving deltas: {scale}%'
                if scale == 100:
                    resolving_spinner.succeed()

        RemoteProgress.update = update

        try:
            Repo.clone_from(url=repo_url, to_path=repo_to_path, depth=1, progress=RemoteProgress())
            for spinner in spinners:
                if spinner.spinner_id is not None and len(spinner.text) != 0:
                    spinner.fail()
            return True
        except GitCommandError as e:
            if e.status == 126:
                echo('Please check your network.')
            elif e.status == 128:
                echo('Please check your Git tool.')
            else:
                raise PunicaException(PunicaError.other_error(e.args[2]))
            return False

    @staticmethod
    def echo_box_help_cmd():
        echo("""

        Commands:

          Compile contracts: punica compile
          Deploy contracts:  punica deploy
          Test contracts:    punica test
        """)

    @staticmethod
    def list_boxes():
        repos_url = 'https://api.github.com/users/punica-box/repos'
        response = requests.get(repos_url).content.decode()
        repos = json.loads(response)
        if isinstance(repos, dict):
            message = repos.get('message', '')
            if 'API rate limit exceeded' in message:
                raise PunicaException(PunicaError.other_error(message))
        name_list = []
        for repo in repos:
            name = repo.get('name', '')
            name_list.append(name)
        return name_list
