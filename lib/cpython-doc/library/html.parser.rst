:mod:`html.parser` --- Simple HTML and XHTML parser
===================================================

.. module:: html.parser
   :synopsis: A simple parser that can handle HTML and XHTML.


.. index::
   single: HTML
   single: XHTML

**Source code:** :source:`Lib/html/parser.py`

--------------

This module defines a class :class:`HTMLParser` which serves as the basis for
parsing text files formatted in HTML (HyperText Mark-up Language) and XHTML.

.. class:: HTMLParser(strict=True)

   Create a parser instance.  If *strict* is ``True`` (the default), invalid
   html results in :exc:`~html.parser.HTMLParseError` exceptions [#]_.  If
   *strict* is ``False``, the parser uses heuristics to make a best guess at
   the intention of any invalid html it encounters, similar to the way most
   browsers do.

   An :class:`HTMLParser` instance is fed HTML data and calls handler functions when tags
   begin and end.  The :class:`HTMLParser` class is meant to be overridden by the
   user to provide a desired behavior.

   This parser does not check that end tags match start tags or call the end-tag
   handler for elements which are closed implicitly by closing an outer element.

   .. versionchanged:: 3.2 *strict* keyword added

An exception is defined as well:


.. exception:: HTMLParseError

   Exception raised by the :class:`HTMLParser` class when it encounters an error
   while parsing.  This exception provides three attributes: :attr:`msg` is a brief
   message explaining the error, :attr:`lineno` is the number of the line on which
   the broken construct was detected, and :attr:`offset` is the number of
   characters into the line at which the construct starts.

:class:`HTMLParser` instances have the following methods:


.. method:: HTMLParser.reset()

   Reset the instance.  Loses all unprocessed data.  This is called implicitly at
   instantiation time.


.. method:: HTMLParser.feed(data)

   Feed some text to the parser.  It is processed insofar as it consists of
   complete elements; incomplete data is buffered until more data is fed or
   :meth:`close` is called.


.. method:: HTMLParser.close()

   Force processing of all buffered data as if it were followed by an end-of-file
   mark.  This method may be redefined by a derived class to define additional
   processing at the end of the input, but the redefined version should always call
   the :class:`HTMLParser` base class method :meth:`close`.


.. method:: HTMLParser.getpos()

   Return current line number and offset.


.. method:: HTMLParser.get_starttag_text()

   Return the text of the most recently opened start tag.  This should not normally
   be needed for structured processing, but may be useful in dealing with HTML "as
   deployed" or for re-generating input with minimal changes (whitespace between
   attributes can be preserved, etc.).


.. method:: HTMLParser.handle_starttag(tag, attrs)

   This method is called to handle the start of a tag.  It is intended to be
   overridden by a derived class; the base class implementation does nothing.

   The *tag* argument is the name of the tag converted to lower case. The *attrs*
   argument is a list of ``(name, value)`` pairs containing the attributes found
   inside the tag's ``<>`` brackets.  The *name* will be translated to lower case,
   and quotes in the *value* have been removed, and character and entity references
   have been replaced.  For instance, for the tag ``<A
   HREF="http://www.cwi.nl/">``, this method would be called as
   ``handle_starttag('a', [('href', 'http://www.cwi.nl/')])``.

   All entity references from :mod:`html.entities` are replaced in the attribute
   values.


.. method:: HTMLParser.handle_startendtag(tag, attrs)

   Similar to :meth:`handle_starttag`, but called when the parser encounters an
   XHTML-style empty tag (``<img ... />``).  This method may be overridden by
   subclasses which require this particular lexical information; the default
   implementation simply calls :meth:`handle_starttag` and :meth:`handle_endtag`.


.. method:: HTMLParser.handle_endtag(tag)

   This method is called to handle the end tag of an element.  It is intended to be
   overridden by a derived class; the base class implementation does nothing.  The
   *tag* argument is the name of the tag converted to lower case.


.. method:: HTMLParser.handle_data(data)

   This method is called to process arbitrary data (e.g. the content of
   ``<script>...</script>`` and ``<style>...</style>``).  It is intended to be
   overridden by a derived class; the base class implementation does nothing.


.. method:: HTMLParser.handle_charref(name)

   This method is called to process a character reference of the form ``&#ref;``.
   It is intended to be overridden by a derived class; the base class
   implementation does nothing.


.. method:: HTMLParser.handle_entityref(name)

   This method is called to process a general entity reference of the form
   ``&name;`` where *name* is an general entity reference.  It is intended to be
   overridden by a derived class; the base class implementation does nothing.


.. method:: HTMLParser.handle_comment(data)

   This method is called when a comment is encountered.  The *comment* argument is
   a string containing the text between the ``--`` and ``--`` delimiters, but not
   the delimiters themselves.  For example, the comment ``<!--text-->`` will cause
   this method to be called with the argument ``'text'``.  It is intended to be
   overridden by a derived class; the base class implementation does nothing.


.. method:: HTMLParser.handle_decl(decl)

   Method called when an SGML ``doctype`` declaration is read by the parser.
   The *decl* parameter will be the entire contents of the declaration inside
   the ``<!...>`` markup.  It is intended to be overridden by a derived class;
   the base class implementation does nothing.


.. method:: HTMLParser.unknown_decl(data)

   Method called when an unrecognized SGML declaration is read by the parser.
   The *data* parameter will be the entire contents of the declaration inside
   the ``<!...>`` markup.  It is sometimes useful to be overridden by a
   derived class; the base class implementation raises an :exc:`HTMLParseError`.


.. method:: HTMLParser.handle_pi(data)

   Method called when a processing instruction is encountered.  The *data*
   parameter will contain the entire processing instruction. For example, for the
   processing instruction ``<?proc color='red'>``, this method would be called as
   ``handle_pi("proc color='red'")``.  It is intended to be overridden by a derived
   class; the base class implementation does nothing.

   .. note::

      The :class:`HTMLParser` class uses the SGML syntactic rules for processing
      instructions.  An XHTML processing instruction using the trailing ``'?'`` will
      cause the ``'?'`` to be included in *data*.


.. _htmlparser-example:

Example HTML Parser Application
-------------------------------

As a basic example, below is a simple HTML parser that uses the
:class:`HTMLParser` class to print out start tags, end tags, and data
as they are encountered::

   from html.parser import HTMLParser

   class MyHTMLParser(HTMLParser):
       def handle_starttag(self, tag, attrs):
           print("Encountered a start tag:", tag)
       def handle_endtag(self, tag):
           print("Encountered  an end tag:", tag)
       def handle_data(self, data):
           print("Encountered   some data:", data)

   parser = MyHTMLParser()
   parser.feed('<html><head><title>Test</title></head>'
               '<body><h1>Parse me!</h1></body></html>')


.. rubric:: Footnotes

.. [#] For backward compatibility reasons *strict* mode does not raise
       exceptions for all non-compliant HTML.  That is, some invalid HTML
       is tolerated even in *strict* mode.
