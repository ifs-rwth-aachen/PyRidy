Usage
=====

.. _installation:

Installation
############

To use PyRidy, first install it using pip:

.. code-block:: console

   (.venv) $ pip install pyridy

File Formats
############

The Ridy Android App can save measurement data in two formats, .rdy and .sqlite. The PyRidy library
can handle both format types and both formats contain the same data and information.

.rdy
    The .rdy format is text-based format which uses the JSON standard and can therefore
    be imported by almost any other programming language. Due to its text-based nature filesizes
    can grow quickly and slows down the saving process. Therefore Ridy currently limits the allowed
    measurement recording time to 10 minutes when the app is set to this format.

.sqlite
    This format contains a SQLite database with the measurement series and some additional tables
    for further information about the measurement. The .sqlite format also does not have a recording time
    limitation. SQLite files are essentially a copy of the database that Ridy uses internally
    to handle measurement data.
