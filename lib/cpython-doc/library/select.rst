:mod:`select` --- Waiting for I/O completion
============================================

.. module:: select
   :synopsis: Wait for I/O completion on multiple streams.


This module provides access to the :c:func:`select` and :c:func:`poll` functions
available in most operating systems, :c:func:`devpoll` available on
Solaris and derivatives, :c:func:`epoll` available on Linux 2.5+ and
:c:func:`kqueue` available on most BSD.
Note that on Windows, it only works for sockets; on other operating systems,
it also works for other file types (in particular, on Unix, it works on pipes).
It cannot be used on regular files to determine whether a file has grown since
it was last read.

The module defines the following:


.. exception:: error

   A deprecated alias of :exc:`OSError`.

   .. versionchanged:: 3.3
      Following :pep:`3151`, this class was made an alias of :exc:`OSError`.


.. function:: devpoll()

   (Only supported on Solaris and derivatives.)  Returns a ``/dev/poll``
   polling object; see section :ref:`devpoll-objects` below for the
   methods supported by devpoll objects.

   :c:func:`devpoll` objects are linked to the number of file
   descriptors allowed at the time of instantiation. If your program
   reduces this value, :c:func:`devpoll` will fail. If your program
   increases this value, :c:func:`devpoll` may return an
   incomplete list of active file descriptors.

   .. versionadded:: 3.3

.. function:: epoll(sizehint=-1, flags=0)

   (Only supported on Linux 2.5.44 and newer.) Return an edge polling object,
   which can be used as Edge or Level Triggered interface for I/O
   events. *sizehint* is deprecated and completely ignored. *flags* can be set
   to :const:`EPOLL_CLOEXEC`, which causes the epoll descriptor to be closed
   automatically when :func:`os.execve` is called. See section
   :ref:`epoll-objects` below for the methods supported by epolling objects.


   .. versionchanged:: 3.3

      Added the *flags* parameter.


.. function:: poll()

   (Not supported by all operating systems.)  Returns a polling object, which
   supports registering and unregistering file descriptors, and then polling them
   for I/O events; see section :ref:`poll-objects` below for the methods supported
   by polling objects.


.. function:: kqueue()

   (Only supported on BSD.)  Returns a kernel queue object; see section
   :ref:`kqueue-objects` below for the methods supported by kqueue objects.


.. function:: kevent(ident, filter=KQ_FILTER_READ, flags=KQ_EV_ADD, fflags=0, data=0, udata=0)

   (Only supported on BSD.)  Returns a kernel event object; see section
   :ref:`kevent-objects` below for the methods supported by kevent objects.


.. function:: select(rlist, wlist, xlist[, timeout])

   This is a straightforward interface to the Unix :c:func:`select` system call.
   The first three arguments are sequences of 'waitable objects': either
   integers representing file descriptors or objects with a parameterless method
   named :meth:`fileno` returning such an integer:

   * *rlist*: wait until ready for reading
   * *wlist*: wait until ready for writing
   * *xlist*: wait for an "exceptional condition" (see the manual page for what
     your system considers such a condition)

   Empty sequences are allowed, but acceptance of three empty sequences is
   platform-dependent. (It is known to work on Unix but not on Windows.)  The
   optional *timeout* argument specifies a time-out as a floating point number
   in seconds.  When the *timeout* argument is omitted the function blocks until
   at least one file descriptor is ready.  A time-out value of zero specifies a
   poll and never blocks.

   The return value is a triple of lists of objects that are ready: subsets of the
   first three arguments.  When the time-out is reached without a file descriptor
   becoming ready, three empty lists are returned.

   .. index::
      single: socket() (in module socket)
      single: popen() (in module os)

   Among the acceptable object types in the sequences are Python :term:`file
   objects <file object>` (e.g. ``sys.stdin``, or objects returned by
   :func:`open` or :func:`os.popen`), socket objects returned by
   :func:`socket.socket`.  You may also define a :dfn:`wrapper` class yourself,
   as long as it has an appropriate :meth:`fileno` method (that really returns
   a file descriptor, not just a random integer).

   .. note::

      .. index:: single: WinSock

      File objects on Windows are not acceptable, but sockets are.  On Windows,
      the underlying :c:func:`select` function is provided by the WinSock
      library, and does not handle file descriptors that don't originate from
      WinSock.

.. attribute:: PIPE_BUF

   The minimum number of bytes which can be written without blocking to a pipe
   when the pipe has been reported as ready for writing by :func:`select`,
   :func:`poll` or another interface in this module.  This doesn't apply
   to other kind of file-like objects such as sockets.

   This value is guaranteed by POSIX to be at least 512.  Availability: Unix.

   .. versionadded:: 3.2


.. _devpoll-objects:

``/dev/poll`` Polling Objects
----------------------------------------------

   http://developers.sun.com/solaris/articles/using_devpoll.html
   http://developers.sun.com/solaris/articles/polling_efficient.html

Solaris and derivatives have ``/dev/poll``. While :c:func:`select` is
O(highest file descriptor) and :c:func:`poll` is O(number of file
descriptors), ``/dev/poll`` is O(active file descriptors).

``/dev/poll`` behaviour is very close to the standard :c:func:`poll`
object.


.. method:: devpoll.register(fd[, eventmask])

   Register a file descriptor with the polling object.  Future calls to the
   :meth:`poll` method will then check whether the file descriptor has any pending
   I/O events.  *fd* can be either an integer, or an object with a :meth:`fileno`
   method that returns an integer.  File objects implement :meth:`fileno`, so they
   can also be used as the argument.

   *eventmask* is an optional bitmask describing the type of events you want to
   check for. The constants are the same that with :c:func:`poll`
   object. The default value is a combination of the constants :const:`POLLIN`,
   :const:`POLLPRI`, and :const:`POLLOUT`.

   .. warning::

      Registering a file descriptor that's already registered is not an
      error, but the result is undefined. The appropiate action is to
      unregister or modify it first. This is an important difference
      compared with :c:func:`poll`.


.. method:: devpoll.modify(fd[, eventmask])

   This method does an :meth:`unregister` followed by a
   :meth:`register`. It is (a bit) more efficient that doing the same
   explicitly.


.. method:: devpoll.unregister(fd)

   Remove a file descriptor being tracked by a polling object.  Just like the
   :meth:`register` method, *fd* can be an integer or an object with a
   :meth:`fileno` method that returns an integer.

   Attempting to remove a file descriptor that was never registered is
   safely ignored.


.. method:: devpoll.poll([timeout])

   Polls the set of registered file descriptors, and returns a possibly-empty list
   containing ``(fd, event)`` 2-tuples for the descriptors that have events or
   errors to report. *fd* is the file descriptor, and *event* is a bitmask with
   bits set for the reported events for that descriptor --- :const:`POLLIN` for
   waiting input, :const:`POLLOUT` to indicate that the descriptor can be written
   to, and so forth. An empty list indicates that the call timed out and no file
   descriptors had any events to report. If *timeout* is given, it specifies the
   length of time in milliseconds which the system will wait for events before
   returning. If *timeout* is omitted, -1, or :const:`None`, the call will
   block until there is an event for this poll object.


.. _epoll-objects:

Edge and Level Trigger Polling (epoll) Objects
----------------------------------------------

   http://linux.die.net/man/4/epoll

   *eventmask*

   +-----------------------+-----------------------------------------------+
   | Constant              | Meaning                                       |
   +=======================+===============================================+
   | :const:`EPOLLIN`      | Available for read                            |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLOUT`     | Available for write                           |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLPRI`     | Urgent data for read                          |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLERR`     | Error condition happened on the assoc. fd     |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLHUP`     | Hang up happened on the assoc. fd             |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLET`      | Set Edge Trigger behavior, the default is     |
   |                       | Level Trigger behavior                        |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLONESHOT` | Set one-shot behavior. After one event is     |
   |                       | pulled out, the fd is internally disabled     |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLRDNORM`  | Equivalent to :const:`EPOLLIN`                |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLRDBAND`  | Priority data band can be read.               |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLWRNORM`  | Equivalent to :const:`EPOLLOUT`               |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLWRBAND`  | Priority data may be written.                 |
   +-----------------------+-----------------------------------------------+
   | :const:`EPOLLMSG`     | Ignored.                                      |
   +-----------------------+-----------------------------------------------+


.. method:: epoll.close()

   Close the control file descriptor of the epoll object.


.. method:: epoll.fileno()

   Return the file descriptor number of the control fd.


.. method:: epoll.fromfd(fd)

   Create an epoll object from a given file descriptor.


.. method:: epoll.register(fd[, eventmask])

   Register a fd descriptor with the epoll object.


.. method:: epoll.modify(fd, eventmask)

   Modify a register file descriptor.


.. method:: epoll.unregister(fd)

   Remove a registered file descriptor from the epoll object.


.. method:: epoll.poll([timeout=-1[, maxevents=-1]])

   Wait for events. timeout in seconds (float)


.. _poll-objects:

Polling Objects
---------------

The :c:func:`poll` system call, supported on most Unix systems, provides better
scalability for network servers that service many, many clients at the same
time. :c:func:`poll` scales better because the system call only requires listing
the file descriptors of interest, while :c:func:`select` builds a bitmap, turns
on bits for the fds of interest, and then afterward the whole bitmap has to be
linearly scanned again. :c:func:`select` is O(highest file descriptor), while
:c:func:`poll` is O(number of file descriptors).


.. method:: poll.register(fd[, eventmask])

   Register a file descriptor with the polling object.  Future calls to the
   :meth:`poll` method will then check whether the file descriptor has any pending
   I/O events.  *fd* can be either an integer, or an object with a :meth:`fileno`
   method that returns an integer.  File objects implement :meth:`fileno`, so they
   can also be used as the argument.

   *eventmask* is an optional bitmask describing the type of events you want to
   check for, and can be a combination of the constants :const:`POLLIN`,
   :const:`POLLPRI`, and :const:`POLLOUT`, described in the table below.  If not
   specified, the default value used will check for all 3 types of events.

   +-------------------+------------------------------------------+
   | Constant          | Meaning                                  |
   +===================+==========================================+
   | :const:`POLLIN`   | There is data to read                    |
   +-------------------+------------------------------------------+
   | :const:`POLLPRI`  | There is urgent data to read             |
   +-------------------+------------------------------------------+
   | :const:`POLLOUT`  | Ready for output: writing will not block |
   +-------------------+------------------------------------------+
   | :const:`POLLERR`  | Error condition of some sort             |
   +-------------------+------------------------------------------+
   | :const:`POLLHUP`  | Hung up                                  |
   +-------------------+------------------------------------------+
   | :const:`POLLNVAL` | Invalid request: descriptor not open     |
   +-------------------+------------------------------------------+

   Registering a file descriptor that's already registered is not an error, and has
   the same effect as registering the descriptor exactly once.


.. method:: poll.modify(fd, eventmask)

   Modifies an already registered fd. This has the same effect as
   ``register(fd, eventmask)``.  Attempting to modify a file descriptor
   that was never registered causes an :exc:`IOError` exception with errno
   :const:`ENOENT` to be raised.


.. method:: poll.unregister(fd)

   Remove a file descriptor being tracked by a polling object.  Just like the
   :meth:`register` method, *fd* can be an integer or an object with a
   :meth:`fileno` method that returns an integer.

   Attempting to remove a file descriptor that was never registered causes a
   :exc:`KeyError` exception to be raised.


.. method:: poll.poll([timeout])

   Polls the set of registered file descriptors, and returns a possibly-empty list
   containing ``(fd, event)`` 2-tuples for the descriptors that have events or
   errors to report. *fd* is the file descriptor, and *event* is a bitmask with
   bits set for the reported events for that descriptor --- :const:`POLLIN` for
   waiting input, :const:`POLLOUT` to indicate that the descriptor can be written
   to, and so forth. An empty list indicates that the call timed out and no file
   descriptors had any events to report. If *timeout* is given, it specifies the
   length of time in milliseconds which the system will wait for events before
   returning. If *timeout* is omitted, negative, or :const:`None`, the call will
   block until there is an event for this poll object.


.. _kqueue-objects:

Kqueue Objects
--------------

.. method:: kqueue.close()

   Close the control file descriptor of the kqueue object.


.. method:: kqueue.fileno()

   Return the file descriptor number of the control fd.


.. method:: kqueue.fromfd(fd)

   Create a kqueue object from a given file descriptor.


.. method:: kqueue.control(changelist, max_events[, timeout=None]) -> eventlist

   Low level interface to kevent

   - changelist must be an iterable of kevent object or None
   - max_events must be 0 or a positive integer
   - timeout in seconds (floats possible)


.. _kevent-objects:

Kevent Objects
--------------

http://www.freebsd.org/cgi/man.cgi?query=kqueue&sektion=2

.. attribute:: kevent.ident

   Value used to identify the event. The interpretation depends on the filter
   but it's usually the file descriptor. In the constructor ident can either
   be an int or an object with a fileno() function. kevent stores the integer
   internally.

.. attribute:: kevent.filter

   Name of the kernel filter.

   +---------------------------+---------------------------------------------+
   | Constant                  | Meaning                                     |
   +===========================+=============================================+
   | :const:`KQ_FILTER_READ`   | Takes a descriptor and returns whenever     |
   |                           | there is data available to read             |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_FILTER_WRITE`  | Takes a descriptor and returns whenever     |
   |                           | there is data available to write            |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_FILTER_AIO`    | AIO requests                                |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_FILTER_VNODE`  | Returns when one or more of the requested   |
   |                           | events watched in *fflag* occurs            |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_FILTER_PROC`   | Watch for events on a process id            |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_FILTER_NETDEV` | Watch for events on a network device        |
   |                           | [not available on Mac OS X]                 |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_FILTER_SIGNAL` | Returns whenever the watched signal is      |
   |                           | delivered to the process                    |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_FILTER_TIMER`  | Establishes an arbitrary timer              |
   +---------------------------+---------------------------------------------+

.. attribute:: kevent.flags

   Filter action.

   +---------------------------+---------------------------------------------+
   | Constant                  | Meaning                                     |
   +===========================+=============================================+
   | :const:`KQ_EV_ADD`        | Adds or modifies an event                   |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_DELETE`     | Removes an event from the queue             |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_ENABLE`     | Permitscontrol() to returns the event       |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_DISABLE`    | Disablesevent                               |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_ONESHOT`    | Removes event after first occurrence        |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_CLEAR`      | Reset the state after an event is retrieved |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_SYSFLAGS`   | internal event                              |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_FLAG1`      | internal event                              |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_EOF`        | Filter specific EOF condition               |
   +---------------------------+---------------------------------------------+
   | :const:`KQ_EV_ERROR`      | See return values                           |
   +---------------------------+---------------------------------------------+


.. attribute:: kevent.fflags

   Filter specific flags.

   :const:`KQ_FILTER_READ` and  :const:`KQ_FILTER_WRITE` filter flags:

   +----------------------------+--------------------------------------------+
   | Constant                   | Meaning                                    |
   +============================+============================================+
   | :const:`KQ_NOTE_LOWAT`     | low water mark of a socket buffer          |
   +----------------------------+--------------------------------------------+

   :const:`KQ_FILTER_VNODE` filter flags:

   +----------------------------+--------------------------------------------+
   | Constant                   | Meaning                                    |
   +============================+============================================+
   | :const:`KQ_NOTE_DELETE`    | *unlink()* was called                      |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_WRITE`     | a write occurred                           |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_EXTEND`    | the file was extended                      |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_ATTRIB`    | an attribute was changed                   |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_LINK`      | the link count has changed                 |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_RENAME`    | the file was renamed                       |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_REVOKE`    | access to the file was revoked             |
   +----------------------------+--------------------------------------------+

   :const:`KQ_FILTER_PROC` filter flags:

   +----------------------------+--------------------------------------------+
   | Constant                   | Meaning                                    |
   +============================+============================================+
   | :const:`KQ_NOTE_EXIT`      | the process has exited                     |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_FORK`      | the process has called *fork()*            |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_EXEC`      | the process has executed a new process     |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_PCTRLMASK` | internal filter flag                       |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_PDATAMASK` | internal filter flag                       |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_TRACK`     | follow a process across *fork()*           |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_CHILD`     | returned on the child process for          |
   |                            | *NOTE_TRACK*                               |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_TRACKERR`  | unable to attach to a child                |
   +----------------------------+--------------------------------------------+

   :const:`KQ_FILTER_NETDEV` filter flags (not available on Mac OS X):

   +----------------------------+--------------------------------------------+
   | Constant                   | Meaning                                    |
   +============================+============================================+
   | :const:`KQ_NOTE_LINKUP`    | link is up                                 |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_LINKDOWN`  | link is down                               |
   +----------------------------+--------------------------------------------+
   | :const:`KQ_NOTE_LINKINV`   | link state is invalid                      |
   +----------------------------+--------------------------------------------+


.. attribute:: kevent.data

   Filter specific data.


.. attribute:: kevent.udata

   User defined value.
