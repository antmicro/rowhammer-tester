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

import sys, os, datetime

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath('.'))

from sphinx_antmicro_theme import __version__, get_html_theme_path
theme_path = get_html_theme_path() + "/sphinx_antmicro_theme"

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
needs_sphinx = '3.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx_tabs.tabs',
    'sphinx_antmicro_theme',
    'sphinx.ext.autosectionlabel',
    'sphinxcontrib.wavedrom',
    'myst_parser'
]
numfig = True
todo_include_todos=False

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'Row Hammer Tester'
_basic_filename = u'rowhammer-tester'
if 'tags' in globals() and 'internal' in tags:
    _basic_filename = 'INTERNAL--' + _basic_filename
authors = u'Antmicro'
copyright = authors + u', 2021-2022'

# The short X.Y version.
version = ''
# The full version, including alpha/beta/rc tags.
release = ''

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%Y-%m-%d'

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# -- Options for HTML output ---------------------------------------------------

render_using_wavedrompy = True

offline_wavedrom_js_path = r"WaveDrom.js"
offline_skin_js_path =  r"default.js"

html_show_sourcelink = True
html_sidebars = {
    "**": ["logo-text.html", "globaltoc.html", "localtoc.html", "searchbox.html"]
}

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'sphinx_antmicro_theme'

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = project

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = theme_path+'/logo-400-html.png'

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = today_fmt

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False

# Output file base name for HTML help builder.
htmlhelp_basename = _basic_filename

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['build/documentation/_static/']

doc_args = '--docs '
#targets = ['zcu104', 'arty']
targets = ['arty']

for t in targets:
    target_script = '../rowhammer_tester/targets/' + t + '.py'
    os.system('python ' + target_script + ' ' + doc_args)

# -- Options for LaTeX output --------------------------------------------------

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', _basic_filename+'.tex', project,
   authors, 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
latex_logo = theme_path+'/logo-400.png'

man_pages = [
    ('index', _basic_filename, project,
     [authors], 1)
]

latex_additional_files = ['%s/%s.sty' % (theme_path,html_theme),latex_logo]

latex_elements = {
    'papersize': 'a4paper',
    'pointsize': '11pt',
    'fontpkg': r'''
        \usepackage{charter}
        \usepackage[defaultsans]{lato}
        \usepackage{inconsolata}
        \usepackage{lscape}
    ''',
    'preamble': r'''
          \usepackage{%s}
          \usepackage{multicol}
    ''' % html_theme,
    'maketitle': r'''
        \renewcommand{\releasename}{}
        \renewcommand{\sphinxlogo}{\includegraphics[height=75pt]{logo-400.png}\par}
        \sphinxmaketitle
    ''',
    'classoptions':',openany,oneside',
    'babel': r'''
          \usepackage[english]{babel}
          \makeatletter
          \@namedef{ver@color.sty}{}
          \makeatother
          \usepackage{silence}
          \WarningFilter{Fancyhdr}{\fancyfoot's `E' option without twoside}
    '''
}

rst_prolog = """
.. role:: raw-latex(raw)
   :format: latex

.. role:: raw-html(raw)
   :format: html
"""

rst_epilog = """
.. |project| replace:: %s
""" % project
