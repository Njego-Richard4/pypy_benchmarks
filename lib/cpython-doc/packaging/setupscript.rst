.. _packaging-setup-script:

************************
Writing the Setup Script
************************

The setup script is the center of all activity in building, distributing, and
installing modules using Distutils.  The main purpose of the setup script is
to describe your module distribution to Distutils, so that the various
commands that operate on your modules do the right thing.  As we saw in section
:ref:`packaging-simple-example`, the setup script consists mainly of a
call to :func:`setup` where the most information is supplied as
keyword arguments to :func:`setup`.

Here's a slightly more involved example, which we'll follow for the next couple
of sections: a setup script that could be used for Packaging itself::

    #!/usr/bin/env python

    from packaging.core import setup, find_packages

    setup(name='Packaging',
          version='1.0',
          summary='Python Distribution Utilities',
          keywords=['packaging', 'packaging'],
          author=u'Tarek Ziadé',
          author_email='tarek@ziade.org',
          home_page='http://bitbucket.org/tarek/packaging/wiki/Home',
          license='PSF',
          packages=find_packages())


There are only two differences between this and the trivial one-file
distribution presented in section :ref:`packaging-simple-example`: more
metadata and the specification of pure Python modules by package rather than
by module.  This is important since Ristutils consist of a couple of dozen
modules split into (so far) two packages; an explicit list of every module
would be tedious to generate and difficult to maintain.  For more information
on the additional metadata, see section :ref:`packaging-metadata`.

Note that any pathnames (files or directories) supplied in the setup script
should be written using the Unix convention, i.e. slash-separated.  The
Distutils will take care of converting this platform-neutral representation into
whatever is appropriate on your current platform before actually using the
pathname.  This makes your setup script portable across operating systems, which
of course is one of the major goals of the Distutils.  In this spirit, all
pathnames in this document are slash-separated.

This, of course, only applies to pathnames given to Distutils functions.  If
you, for example, use standard Python functions such as :func:`glob.glob` or
:func:`os.listdir` to specify files, you should be careful to write portable
code instead of hardcoding path separators::

    glob.glob(os.path.join('mydir', 'subdir', '*.html'))
    os.listdir(os.path.join('mydir', 'subdir'))


.. _packaging-listing-packages:

Listing whole packages
======================

The :option:`packages` option tells the Distutils to process (build, distribute,
install, etc.) all pure Python modules found in each package mentioned in the
:option:`packages` list.  In order to do this, of course, there has to be a
correspondence between package names and directories in the filesystem.  The
default correspondence is the most obvious one, i.e. package :mod:`packaging` is
found in the directory :file:`packaging` relative to the distribution root.
Thus, when you say ``packages = ['foo']`` in your setup script, you are
promising that the Distutils will find a file :file:`foo/__init__.py` (which
might be spelled differently on your system, but you get the idea) relative to
the directory where your setup script lives.  If you break this promise, the
Distutils will issue a warning but still process the broken package anyway.

If you use a different convention to lay out your source directory, that's no
problem: you just have to supply the :option:`package_dir` option to tell the
Distutils about your convention.  For example, say you keep all Python source
under :file:`lib`, so that modules in the "root package" (i.e., not in any
package at all) are in :file:`lib`, modules in the :mod:`foo` package are in
:file:`lib/foo`, and so forth.  Then you would put ::

    package_dir = {'': 'lib'}

in your setup script.  The keys to this dictionary are package names, and an
empty package name stands for the root package.  The values are directory names
relative to your distribution root.  In this case, when you say ``packages =
['foo']``, you are promising that the file :file:`lib/foo/__init__.py` exists.

Another possible convention is to put the :mod:`foo` package right in
:file:`lib`, the :mod:`foo.bar` package in :file:`lib/bar`, etc.  This would be
written in the setup script as ::

    package_dir = {'foo': 'lib'}

A ``package: dir`` entry in the :option:`package_dir` dictionary implicitly
applies to all packages below *package*, so the :mod:`foo.bar` case is
automatically handled here.  In this example, having ``packages = ['foo',
'foo.bar']`` tells the Distutils to look for :file:`lib/__init__.py` and
:file:`lib/bar/__init__.py`.  (Keep in mind that although :option:`package_dir`
applies recursively, you must explicitly list all packages in
:option:`packages`: the Distutils will *not* recursively scan your source tree
looking for any directory with an :file:`__init__.py` file.)


.. _packaging-listing-modules:

Listing individual modules
==========================

For a small module distribution, you might prefer to list all modules rather
than listing packages---especially the case of a single module that goes in the
"root package" (i.e., no package at all).  This simplest case was shown in
section :ref:`packaging-simple-example`; here is a slightly more involved
example::

    py_modules = ['mod1', 'pkg.mod2']

This describes two modules, one of them in the "root" package, the other in the
:mod:`pkg` package.  Again, the default package/directory layout implies that
these two modules can be found in :file:`mod1.py` and :file:`pkg/mod2.py`, and
that :file:`pkg/__init__.py` exists as well. And again, you can override the
package/directory correspondence using the :option:`package_dir` option.


.. _packaging-describing-extensions:

Describing extension modules
============================

Just as writing Python extension modules is a bit more complicated than writing
pure Python modules, describing them to the Distutils is a bit more complicated.
Unlike pure modules, it's not enough just to list modules or packages and expect
the Distutils to go out and find the right files; you have to specify the
extension name, source file(s), and any compile/link requirements (include
directories, libraries to link with, etc.).

.. XXX read over this section

All of this is done through another keyword argument to :func:`setup`, the
:option:`ext_modules` option.  :option:`ext_modules` is just a list of
:class:`Extension` instances, each of which describes a single extension module.
Suppose your distribution includes a single extension, called :mod:`foo` and
implemented by :file:`foo.c`.  If no additional instructions to the
compiler/linker are needed, describing this extension is quite simple::

    Extension('foo', ['foo.c'])

The :class:`Extension` class can be imported from :mod:`packaging.core` along
with :func:`setup`.  Thus, the setup script for a module distribution that
contains only this one extension and nothing else might be::

    from packaging.core import setup, Extension
    setup(name='foo',
          version='1.0',
          ext_modules=[Extension('foo', ['foo.c'])])

The :class:`Extension` class (actually, the underlying extension-building
machinery implemented by the :command:`build_ext` command) supports a great deal
of flexibility in describing Python extensions, which is explained in the
following sections.


Extension names and packages
----------------------------

The first argument to the :class:`Extension` constructor is always the name of
the extension, including any package names.  For example, ::

    Extension('foo', ['src/foo1.c', 'src/foo2.c'])

describes an extension that lives in the root package, while ::

    Extension('pkg.foo', ['src/foo1.c', 'src/foo2.c'])

describes the same extension in the :mod:`pkg` package.  The source files and
resulting object code are identical in both cases; the only difference is where
in the filesystem (and therefore where in Python's namespace hierarchy) the
resulting extension lives.

If your distribution contains only one or more extension modules in a package,
you need to create a :file:`{package}/__init__.py` file anyway, otherwise Python
won't be able to import anything.

If you have a number of extensions all in the same package (or all under the
same base package), use the :option:`ext_package` keyword argument to
:func:`setup`.  For example, ::

    setup(...,
          ext_package='pkg',
          ext_modules=[Extension('foo', ['foo.c']),
                       Extension('subpkg.bar', ['bar.c'])])

will compile :file:`foo.c` to the extension :mod:`pkg.foo`, and :file:`bar.c` to
:mod:`pkg.subpkg.bar`.


Extension source files
----------------------

The second argument to the :class:`Extension` constructor is a list of source
files.  Since the Distutils currently only support C, C++, and Objective-C
extensions, these are normally C/C++/Objective-C source files.  (Be sure to use
appropriate extensions to distinguish C++\ source files: :file:`.cc` and
:file:`.cpp` seem to be recognized by both Unix and Windows compilers.)

However, you can also include SWIG interface (:file:`.i`) files in the list; the
:command:`build_ext` command knows how to deal with SWIG extensions: it will run
SWIG on the interface file and compile the resulting C/C++ file into your
extension.

.. XXX SWIG support is rough around the edges and largely untested!

This warning notwithstanding, options to SWIG can be currently passed like
this::

    setup(...,
          ext_modules=[Extension('_foo', ['foo.i'],
                                 swig_opts=['-modern', '-I../include'])],
          py_modules=['foo'])

Or on the command line like this::

    > python setup.py build_ext --swig-opts="-modern -I../include"

On some platforms, you can include non-source files that are processed by the
compiler and included in your extension.  Currently, this just means Windows
message text (:file:`.mc`) files and resource definition (:file:`.rc`) files for
Visual C++. These will be compiled to binary resource (:file:`.res`) files and
linked into the executable.


Preprocessor options
--------------------

Three optional arguments to :class:`Extension` will help if you need to specify
include directories to search or preprocessor macros to define/undefine:
``include_dirs``, ``define_macros``, and ``undef_macros``.

For example, if your extension requires header files in the :file:`include`
directory under your distribution root, use the ``include_dirs`` option::

    Extension('foo', ['foo.c'], include_dirs=['include'])

You can specify absolute directories there; if you know that your extension will
only be built on Unix systems with X11R6 installed to :file:`/usr`, you can get
away with ::

    Extension('foo', ['foo.c'], include_dirs=['/usr/include/X11'])

You should avoid this sort of non-portable usage if you plan to distribute your
code: it's probably better to write C code like  ::

    #include <X11/Xlib.h>

If you need to include header files from some other Python extension, you can
take advantage of the fact that header files are installed in a consistent way
by the Distutils :command:`install_header` command.  For example, the Numerical
Python header files are installed (on a standard Unix installation) to
:file:`/usr/local/include/python1.5/Numerical`. (The exact location will differ
according to your platform and Python installation.)  Since the Python include
directory---\ :file:`/usr/local/include/python1.5` in this case---is always
included in the search path when building Python extensions, the best approach
is to write C code like  ::

    #include <Numerical/arrayobject.h>

.. TODO check if it's d2.sysconfig or the new sysconfig module now

If you must put the :file:`Numerical` include directory right into your header
search path, though, you can find that directory using the Distutils
:mod:`packaging.sysconfig` module::

    from packaging.sysconfig import get_python_inc
    incdir = os.path.join(get_python_inc(plat_specific=1), 'Numerical')
    setup(...,
          Extension(..., include_dirs=[incdir]))

Even though this is quite portable---it will work on any Python installation,
regardless of platform---it's probably easier to just write your C code in the
sensible way.

You can define and undefine preprocessor macros with the ``define_macros`` and
``undef_macros`` options. ``define_macros`` takes a list of ``(name, value)``
tuples, where ``name`` is the name of the macro to define (a string) and
``value`` is its value: either a string or ``None``.  (Defining a macro ``FOO``
to ``None`` is the equivalent of a bare ``#define FOO`` in your C source: with
most compilers, this sets ``FOO`` to the string ``1``.)  ``undef_macros`` is
just a list of macros to undefine.

For example::

    Extension(...,
              define_macros=[('NDEBUG', '1'),
                             ('HAVE_STRFTIME', None)],
              undef_macros=['HAVE_FOO', 'HAVE_BAR'])

is the equivalent of having this at the top of every C source file::

    #define NDEBUG 1
    #define HAVE_STRFTIME
    #undef HAVE_FOO
    #undef HAVE_BAR


Library options
---------------

You can also specify the libraries to link against when building your extension,
and the directories to search for those libraries.  The ``libraries`` option is
a list of libraries to link against, ``library_dirs`` is a list of directories
to search for libraries at  link-time, and ``runtime_library_dirs`` is a list of
directories to  search for shared (dynamically loaded) libraries at run-time.

For example, if you need to link against libraries known to be in the standard
library search path on target systems ::

    Extension(...,
              libraries=['gdbm', 'readline'])

If you need to link with libraries in a non-standard location, you'll have to
include the location in ``library_dirs``::

    Extension(...,
              library_dirs=['/usr/X11R6/lib'],
              libraries=['X11', 'Xt'])

(Again, this sort of non-portable construct should be avoided if you intend to
distribute your code.)

.. XXX Should mention clib libraries here or somewhere else!


Other options
-------------

There are still some other options which can be used to handle special cases.

The :option:`optional` option is a boolean; if it is true,
a build failure in the extension will not abort the build process, but
instead simply not install the failing extension.

The :option:`extra_objects` option is a list of object files to be passed to the
linker. These files must not have extensions, as the default extension for the
compiler is used.

:option:`extra_compile_args` and :option:`extra_link_args` can be used to
specify additional command-line options for the respective compiler and linker
command lines.

:option:`export_symbols` is only useful on Windows.  It can contain a list of
symbols (functions or variables) to be exported. This option is not needed when
building compiled extensions: Distutils  will automatically add ``initmodule``
to the list of exported symbols.

The :option:`depends` option is a list of files that the extension depends on
(for example header files). The build command will call the compiler on the
sources to rebuild extension if any on this files has been modified since the
previous build.

Relationships between Distributions and Packages
================================================

.. FIXME rewrite to update to PEP 345 (but without dist/release confusion)

A distribution may relate to packages in three specific ways:

#. It can require packages or modules.

#. It can provide packages or modules.

#. It can obsolete packages or modules.

These relationships can be specified using keyword arguments to the
:func:`packaging.core.setup` function.

Dependencies on other Python modules and packages can be specified by supplying
the *requires* keyword argument to :func:`setup`. The value must be a list of
strings.  Each string specifies a package that is required, and optionally what
versions are sufficient.

To specify that any version of a module or package is required, the string
should consist entirely of the module or package name. Examples include
``'mymodule'`` and ``'xml.parsers.expat'``.

If specific versions are required, a sequence of qualifiers can be supplied in
parentheses.  Each qualifier may consist of a comparison operator and a version
number.  The accepted comparison operators are::

    <    >    ==
    <=   >=   !=

These can be combined by using multiple qualifiers separated by commas (and
optional whitespace).  In this case, all of the qualifiers must be matched; a
logical AND is used to combine the evaluations.

Let's look at a bunch of examples:

+-------------------------+----------------------------------------------+
| Requires Expression     | Explanation                                  |
+=========================+==============================================+
| ``==1.0``               | Only version ``1.0`` is compatible           |
+-------------------------+----------------------------------------------+
| ``>1.0, !=1.5.1, <2.0`` | Any version after ``1.0`` and before ``2.0`` |
|                         | is compatible, except ``1.5.1``              |
+-------------------------+----------------------------------------------+

Now that we can specify dependencies, we also need to be able to specify what we
provide that other distributions can require.  This is done using the *provides*
keyword argument to :func:`setup`. The value for this keyword is a list of
strings, each of which names a Python module or package, and optionally
identifies the version.  If the version is not specified, it is assumed to match
that of the distribution.

Some examples:

+---------------------+----------------------------------------------+
| Provides Expression | Explanation                                  |
+=====================+==============================================+
| ``mypkg``           | Provide ``mypkg``, using the distribution    |
|                     | version                                      |
+---------------------+----------------------------------------------+
| ``mypkg (1.1)``     | Provide ``mypkg`` version 1.1, regardless of |
|                     | the distribution version                     |
+---------------------+----------------------------------------------+

A package can declare that it obsoletes other packages using the *obsoletes*
keyword argument.  The value for this is similar to that of the *requires*
keyword: a list of strings giving module or package specifiers.  Each specifier
consists of a module or package name optionally followed by one or more version
qualifiers.  Version qualifiers are given in parentheses after the module or
package name.

The versions identified by the qualifiers are those that are obsoleted by the
distribution being described.  If no qualifiers are given, all versions of the
named module or package are understood to be obsoleted.

.. _packaging-installing-scripts:

Installing Scripts
==================

So far we have been dealing with pure and non-pure Python modules, which are
usually not run by themselves but imported by scripts.

Scripts are files containing Python source code, intended to be started from the
command line.  Scripts don't require Distutils to do anything very complicated.
The only clever feature is that if the first line of the script starts with
``#!`` and contains the word "python", the Distutils will adjust the first line
to refer to the current interpreter location. By default, it is replaced with
the current interpreter location.  The :option:`--executable` (or :option:`-e`)
option will allow the interpreter path to be explicitly overridden.

The :option:`scripts` option simply is a list of files to be handled in this
way.  From the PyXML setup script::

    setup(...,
          scripts=['scripts/xmlproc_parse', 'scripts/xmlproc_val'])

All the scripts will also be added to the ``MANIFEST`` file if no template is
provided. See :ref:`packaging-manifest`.

.. _packaging-installing-package-data:

Installing Package Data
=======================

Often, additional files need to be installed into a package.  These files are
often data that's closely related to the package's implementation, or text files
containing documentation that might be of interest to programmers using the
package.  These files are called :dfn:`package data`.

Package data can be added to packages using the ``package_data`` keyword
argument to the :func:`setup` function.  The value must be a mapping from
package name to a list of relative path names that should be copied into the
package.  The paths are interpreted as relative to the directory containing the
package (information from the ``package_dir`` mapping is used if appropriate);
that is, the files are expected to be part of the package in the source
directories. They may contain glob patterns as well.

The path names may contain directory portions; any necessary directories will be
created in the installation.

For example, if a package should contain a subdirectory with several data files,
the files can be arranged like this in the source tree::

    setup.py
    src/
        mypkg/
              __init__.py
              module.py
              data/
                   tables.dat
                   spoons.dat
                   forks.dat

The corresponding call to :func:`setup` might be::

    setup(...,
          packages=['mypkg'],
          package_dir={'mypkg': 'src/mypkg'},
          package_data={'mypkg': ['data/*.dat']})


All the files that match ``package_data`` will be added to the ``MANIFEST``
file if no template is provided. See :ref:`packaging-manifest`.


.. _packaging-additional-files:

Installing Additional Files
===========================

The :option:`data_files` option can be used to specify additional files needed
by the module distribution: configuration files, message catalogs, data files,
anything which doesn't fit in the previous categories.

:option:`data_files` specifies a sequence of (*directory*, *files*) pairs in the
following way::

    setup(...,
          data_files=[('bitmaps', ['bm/b1.gif', 'bm/b2.gif']),
                      ('config', ['cfg/data.cfg']),
                      ('/etc/init.d', ['init-script'])])

Note that you can specify the directory names where the data files will be
installed, but you cannot rename the data files themselves.

Each (*directory*, *files*) pair in the sequence specifies the installation
directory and the files to install there.  If *directory* is a relative path, it
is interpreted relative to the installation prefix (Python's ``sys.prefix`` for
pure-Python packages, ``sys.exec_prefix`` for packages that contain extension
modules).  Each file name in *files* is interpreted relative to the
:file:`setup.py` script at the top of the package source distribution.  No
directory information from *files* is used to determine the final location of
the installed file; only the name of the file is used.

You can specify the :option:`data_files` options as a simple sequence of files
without specifying a target directory, but this is not recommended, and the
:command:`install_dist` command will print a warning in this case. To install data
files directly in the target directory, an empty string should be given as the
directory.

All the files that match ``data_files`` will be added to the ``MANIFEST`` file
if no template is provided. See :ref:`packaging-manifest`.



.. _packaging-metadata:

Metadata reference
==================

The setup script may include additional metadata beyond the name and version.
This table describes required and additional information:

.. TODO synchronize with setupcfg; link to it (but don't remove it, it's a
   useful summary)

+----------------------+---------------------------+-----------------+--------+
| Meta-Data            | Description               | Value           | Notes  |
+======================+===========================+=================+========+
| ``name``             | name of the project       | short string    | \(1)   |
+----------------------+---------------------------+-----------------+--------+
| ``version``          | version of this release   | short string    | (1)(2) |
+----------------------+---------------------------+-----------------+--------+
| ``author``           | project author's name     | short string    | \(3)   |
+----------------------+---------------------------+-----------------+--------+
| ``author_email``     | email address of the      | email address   | \(3)   |
|                      | project author            |                 |        |
+----------------------+---------------------------+-----------------+--------+
| ``maintainer``       | project maintainer's name | short string    | \(3)   |
+----------------------+---------------------------+-----------------+--------+
| ``maintainer_email`` | email address of the      | email address   | \(3)   |
|                      | project maintainer        |                 |        |
+----------------------+---------------------------+-----------------+--------+
| ``home_page``        | home page for the project | URL             | \(1)   |
+----------------------+---------------------------+-----------------+--------+
| ``summary``          | short description of the  | short string    |        |
|                      | project                   |                 |        |
+----------------------+---------------------------+-----------------+--------+
| ``description``      | longer description of the | long string     | \(5)   |
|                      | project                   |                 |        |
+----------------------+---------------------------+-----------------+--------+
| ``download_url``     | location where the        | URL             |        |
|                      | project may be downloaded |                 |        |
+----------------------+---------------------------+-----------------+--------+
| ``classifiers``      | a list of classifiers     | list of strings | \(4)   |
+----------------------+---------------------------+-----------------+--------+
| ``platforms``        | a list of platforms       | list of strings |        |
+----------------------+---------------------------+-----------------+--------+
| ``license``          | license for the release   | short string    | \(6)   |
+----------------------+---------------------------+-----------------+--------+

Notes:

(1)
    These fields are required.

(2)
    It is recommended that versions take the form *major.minor[.patch[.sub]]*.

(3)
    Either the author or the maintainer must be identified.

(4)
    The list of classifiers is available from the `PyPI website
    <http://pypi.python.org/pypi>`_. See also :mod:`packaging.create`.

(5)
    The ``description`` field is used by PyPI when you are registering a
    release, to build its PyPI page.

(6)
    The ``license`` field is a text indicating the license covering the
    distribution where the license is not a selection from the "License" Trove
    classifiers. See the ``Classifier`` field. Notice that
    there's a ``licence`` distribution option which is deprecated but still
    acts as an alias for ``license``.

'short string'
    A single line of text, not more than 200 characters.

'long string'
    Multiple lines of plain text in reStructuredText format (see
    http://docutils.sf.net/).

'list of strings'
    See below.

In Python 2.x, "string value" means a unicode object. If a byte string (str or
bytes) is given, it has to be valid ASCII.

.. TODO move this section to the version document, keep a summary, add a link

Encoding the version information is an art in itself. Python projects generally
adhere to the version format *major.minor[.patch][sub]*. The major number is 0
for initial, experimental releases of software. It is incremented for releases
that represent major milestones in a project. The minor number is incremented
when important new features are added to the project. The patch number
increments when bug-fix releases are made. Additional trailing version
information is sometimes used to indicate sub-releases.  These are
"a1,a2,...,aN" (for alpha releases, where functionality and API may change),
"b1,b2,...,bN" (for beta releases, which only fix bugs) and "pr1,pr2,...,prN"
(for final pre-release release testing). Some examples:

0.1.0
    the first, experimental release of a project

1.0.1a2
    the second alpha release of the first patch version of 1.0

:option:`classifiers` are specified in a Python list::

    setup(...,
          classifiers=[
              'Development Status :: 4 - Beta',
              'Environment :: Console',
              'Environment :: Web Environment',
              'Intended Audience :: End Users/Desktop',
              'Intended Audience :: Developers',
              'Intended Audience :: System Administrators',
              'License :: OSI Approved :: Python Software Foundation License',
              'Operating System :: MacOS :: MacOS X',
              'Operating System :: Microsoft :: Windows',
              'Operating System :: POSIX',
              'Programming Language :: Python',
              'Topic :: Communications :: Email',
              'Topic :: Office/Business',
              'Topic :: Software Development :: Bug Tracking',
              ])


Debugging the setup script
==========================

Sometimes things go wrong, and the setup script doesn't do what the developer
wants.

Distutils catches any exceptions when running the setup script, and print a
simple error message before the script is terminated.  The motivation for this
behaviour is to not confuse administrators who don't know much about Python and
are trying to install a project.  If they get a big long traceback from deep
inside the guts of Distutils, they may think the project or the Python
installation is broken because they don't read all the way down to the bottom
and see that it's a permission problem.

.. FIXME DISTUTILS_DEBUG is dead, document logging/warnings here

On the other hand, this doesn't help the developer to find the cause of the
failure. For this purpose, the DISTUTILS_DEBUG environment variable can be set
to anything except an empty string, and Packaging will now print detailed
information about what it is doing, and prints the full traceback in case an
exception occurs.
