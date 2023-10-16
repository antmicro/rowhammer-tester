#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022  Antmicro
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from subprocess import run

from antmicro_sphinx_utils.defaults import (
    extensions as default_extensions,
    myst_enable_extensions as default_myst_enable_extensions,
    antmicro_html,
    antmicro_latex
)

# -- General configuration -----------------------------------------------------

# General information about the project.
project = u'Rowhammer tester'
basic_filename = u'rowhammer-tester'
if 'tags' in globals() and 'internal' in tags:
    basic_filename = 'INTERNAL--' + basic_filename
authors = u'Antmicro'
copyright = authors + u', 2021-2023'

# The short X.Y version.
version = ''
# The full version, including alpha/beta/rc tags.
release = ''

# This is temporary before the clash between myst-parser and immaterial is fixed
sphinx_immaterial_override_builtin_admonitions = False

numfig = True

extensions = list(set(default_extensions + [
    'sphinx_tabs.tabs',
    'sphinx.ext.autosectionlabel',
    'sphinxcontrib.wavedrom',
]))

# Supress duplicate label warnings from autosectionlabel
suppress_warnings = ['autosectionlabel.*']

myst_enable_extensions = default_myst_enable_extensions

myst_substitutions = {
    "project": project
}

today_fmt = '%Y-%m-%d'

todo_include_todos=False

# -- Options for HTML output ---------------------------------------------------

html_theme = 'sphinx_immaterial'

html_last_updated_fmt = today_fmt

html_show_sphinx = False

html_title = project

(
    html_logo,
    html_theme_options,
    html_context
) = antmicro_html(
    gh_slug="antmicro/rowhammer-tester",
    pdf_url=f"{basic_filename}.pdf"
)

render_using_wavedrompy = True

offline_wavedrom_js_path = r"WaveDrom.js"
offline_skin_js_path =  r"default.js"

html_show_sourcelink = True
html_sidebars = {
    "**": ["logo-text.html", "globaltoc.html", "localtoc.html", "searchbox.html"]
}

html_static_path = ['build/arty/documentation/_static/']

for target in ['arty', 'zcu104', 'ddr4_datacenter_test_board',
    'lpddr4_test_board', 'ddr5_test_board','ddr5_tester']:
    run([
        'python3',
        f'../../rowhammer_tester/targets/{target}.py',
        '--docs',
    ])
    run([
        'cp',
        f'images/{target}_CRG.png',
        f'build/{target}/documentation/{target}_CRG.png',
    ])

# -- Options for LaTeX output --------------------------------------------------

(
    latex_elements,
    latex_documents,
    latex_logo,
    latex_additional_files
) = antmicro_latex(basic_filename, project, authors)

# -- Options for man output ----------------------------------------------------

man_pages = [
    ('index', basic_filename, project,
     [authors], 1)
]
