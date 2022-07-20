# PyRidy

![alt text](assets/ic_launcher.png "PyRidy Logo")

Python Support Library to import and process Ridy files

### About Ridy
Ridy is an Android App to record sensor data for uses in science and engineering. The app is currently actively being 
developed at the [Chair and Institute for Rail Vehicles and Transport Systems (IFS)](http://www.ifs.rwth-aachen.de/en/start/)

<img src="assets/screenshot.png" alt="Ridy Screenshot" width="200"/>

At the institute Ridy is e.g. used for condition monitoring of railway tracks and several more use-cases are currently
researched upon.
Among other, Ridy can record:
* Acceleration
* Linear Acceleration (i.e., without g-Force)
* Magnetic Field
* Gyroscope
* Orientation
* GNSS Location (+ Android Raw GNSS Measurements)
* Pressure, Humidity, Temperature, Ambient Light

Compared to other existing apps Ridy can perform long measurements even in the background when the phone is locked.
The app supports two formats for data export, JSON and SQLITE. If you would like to use or try out the app please contact the
developer (see below) to get access.

### About PyRidy
PyRidy is the companion python library for the Ridy Android App. It provides easy access to the data no matter which
recording format was used. If pyridy is used, one does no longer need to manually write code to import the files.

In addition, pyridy provides several more features:
* Automatic conversion of sensor data into objects and numpy arrays
* Conversion of arrays to Pandas DataFrame objects
* Time synchronization of individual files (e.g. from different phones)
* Download of OSM Railway Data via the Overpass API
* Plotting of GPS tracks onto a map using ipyleaflet

### Documentation
[PyRidy Documentation](https://pyridy.readthedocs.io/)
#### Installation

Install using pip
```python
    pip install pyridy
```

#### Usage

Information and examples on how to use the library can be found in the [PyRidy documentation](https://pyridy.readthedocs.io/)

### Developer
Philipp Leibner - philipp.leibner@ifs.rwth-aachen.de

### Contributor
Daniel Pujiula Buhl - daniel.pujiula@rwth-aachen.de

<div>  
<a href="">
    <img src="assets/ifs_logo_rgb.svg" alt="IFS Logo" width="400">
  </a>
</div>
