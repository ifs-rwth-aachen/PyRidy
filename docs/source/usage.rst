Usage
=====

.. _installation:

Installation
############

To use PyRidy, first install it using pip:

.. code-block:: console

   pip install pyridy

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


Data Format
############

SQLite database is used to store and manage the measurements. This is the data stored on the Android device.
The documentation of the `Android SDK <https://developer.android.com/reference/android/database/package-summary>`_ provides further information.
The database contains the following entries:

.. list-table:: Measurements
   :widths: 25 70

   * - **acc_measurements_table**
     - Table containing acceleration values. It contains the timestamps as well as the acceleration values according to x- y- and z-axis.

   * - **device_information_table**
     - Table containing device information such as model, product, device, manufacturer, brand, base operating system and api level.

   * - **gps_measurements_table**
     - Table containing GPS values; timestamps, latitude, longitude, altitude,  the bearing at the time in degrees, the speed at the time of this location in meters per second, the estimated horizontal accuracy radius in meters, the estimated altitude accuracy in meters, the estimated bearing accuracy in degrees, the estimated speed accuracy in meters per second and the time in utc.

   * - **gyro_measurements_table**
     - Table containing the rate of rotation around x- y- and z-axis along with the timestamps.

   * - **humidity_measurements_table**
     - Table contaning the ambient relative humidity and the corresponding timestamps.

   * - **light_measurements_table**
     - Table containing the light measurements and the corresponding timestamps.

   * - **lin_acc_measurements_table**
     - Table containing linear acceleration values (i.e without g) along x- y- and z-axis and the corresponding timestamps.

   * - **mag_measurements_table**
     - Table containing magnetic field values along x- y- and z-axis as well as the corresponding timestamps.

   * - **measurement_information_table**
     - Table containing information about the measurements, such as the timestamps when started and stopped, the rdy-format version, name. sex, age, height and weight?

   * - **orient_measurements_table**
     - Table containing orientation values; azimuth, pitch and roll angles and the corresponding timestamps.

   * - **pressure_measurements_table**
     - Table containing the ambient air pressure and the timestamps.

   * - **rot_measurements_table**
     - Table containing rotation vectors along x-, y- and z-axis, the scalar component of the rotation vector and the heading acceleration?

   * - **sensor_descriptions_table**
     - Table containing sensor information including: the vendor's name, sensor's type string, power in mA, resolution, version, generic type, the delay between two sensor events corresponding to the lowest frequency that this sensor supports, the maximum range of the sensor in the sensor's unit and the minimum delay allowed between two events in microseconds or zero if this sensor only returns a value when the data it's measuring changes.

   * - **subjective_comfort_measurements_table**
     - Table containing the subjective comfort values and their timestamps.

   * - **temperature_measurements_table**
     - Table containing the ambient temperature and the corresponding timestamps.

   * - **wz_measurements_table**
     - Table containing the Sperling's ride index's values to determine ride Comfort.

