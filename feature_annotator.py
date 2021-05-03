# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FeatureAnnotator
                                 A QGIS plugin
 Helps annotating geo-features with labels
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-04-29
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Jonathan Gerbscheid
        email                : jonathan@youngmavericks.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os.path
from .resources import *

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject
from qgis.core import QgsVectorLayer, QgsMessageLog, QgsVectorDataProvider, QgsField, QgsRectangle

# Initialize Qt resources from file resources.py
# Import the code for the dialog
from .feature_annotator_dialog import FeatureAnnotatorDialog


class FeatureAnnotator:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interfac
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FeatureAnnotator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Feature Annotator')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.feature_index = 0
        self.labeling_started = False
        self.canvas = self.iface.mapCanvas()
        self.classes = set()
        self.dlg = FeatureAnnotatorDialog()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FeatureAnnotator', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/feature_annotator/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Annotate features'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Feature Annotator'),
                action)
            self.iface.removeToolBarIcon(action)

    @staticmethod
    def get_vectorlayers():
        """
        Get vector layers in project.
        """
        layers = QgsProject.instance().mapLayers().values()
        vectorlayers = [layer for layer in layers if type(layer) == QgsVectorLayer]
        return vectorlayers

    def populate_sourcelayercbox(self):
        """
        Add all the available vecotr layers to the source layer combobox.
        """
        # Fetch the currently loaded layers
        layers = QgsProject.instance().mapLayers().values()

        # Clear the contents of the sourcelayercbox from previous runs
        self.dlg.sourcelayercbox.clear()

        # Populate the comboBox with names of all the loaded layers
        vectorlayers = [layer for layer in layers if type(layer) == QgsVectorLayer]
        self.dlg.sourcelayercbox.addItems([layer.name() for layer in vectorlayers])
        # QgsMessageLog.logMessage("populated vectorlayers", "feature_annotator")

    def populate_fieldsbox(self):
        """
        Add all fieldnames in selected vector layer to the field selection combobox.
        """
        vectorlayers = self.get_vectorlayers()
        vectorlayer = vectorlayers[self.dlg.sourcelayercbox.currentIndex()]
        fields = vectorlayer.fields()
        self.dlg.sourcelayercbox.addItems([field.name() for field in fields])

    def add_field(self):
        """
        Add field to currently selected vectorlayer using info from the GUI.
        """
        vectorlayers = self.get_vectorlayers()
        layer = vectorlayers[self.dlg.sourcelayercbox.currentIndex()]
        fieldname = str(self.dlg.featurenameinput.text())

        # add a string field with fieldname to the layer.
        caps = layer.dataProvider().capabilities()
        if caps & QgsVectorDataProvider.AddAttributes:
            layer.dataProvider().addAttributes([QgsField(fieldname, QVariant.String)])

        # set the value for all the entries of this field to the default value
        # giving in the GUI. (if there is a way to pass this default please tell me :P)
        layer.updateFields()
        layer.selectAll()
        selection = layer.selectedFeatures()
        fields = layer.fields()
        field_idx = len(fields) - 1
        for i, feat in enumerate(selection):
            layer.dataProvider().changeAttributeValues({i: {field_idx: str(self.dlg.default_feat_value.displayText())}})
        layer.removeSelection()
        # update values in the selected dropdown box
        self.source_select()

    def source_select(self):
        """
        Update options in field selection combobox when a new field is added.
        """
        vectorlayers = self.get_vectorlayers()
        self.dlg.selectedannname.clear()
        selected_layer_index = self.dlg.sourcelayercbox.currentIndex()
        selected_layer = vectorlayers[selected_layer_index]
        fields = [field.name() for field in selected_layer.fields()]
        self.dlg.selectedannname.addItems(fields)

    def populate_class_lists(self):
        """
        Update possible classes in the class listview and the class combobox in the labeling section.
        """
        self.populate_class_cbox()
        self.populate_class_listview()

    def populate_class_cbox(self):
        """
        Update possible classes in the annotation combobox.
        """
        self.dlg.annotationcbox.clear()
        sorted_classes = sorted(list([c for c in self.classes]))
        self.dlg.annotationcbox.addItems([str(i) for i in sorted_classes])

    def populate_class_listview(self):
        """
        Update possible classes in the classlist box.
        """
        self.dlg.classlist.clear()
        sorted_classes = sorted(list([c for c in self.classes]))
        self.dlg.classlist.addItems([str(i) for i in sorted_classes])

    def add_class(self):
        """
        Add class to possible classes.
        """
        self.classes.add(self.dlg.labelinput.text())
        self.populate_class_lists()

    def get_classes_from_field(self):
        """
        Get all occuring classes from selected field and add them to the classlist.
        """
        vectorlayers = self.get_vectorlayers()
        vectorlayer = vectorlayers[self.dlg.sourcelayercbox.currentIndex()]

        selected_field_index = self.dlg.selectedannname.currentIndex()

        vectorlayer.selectAll()
        selection = vectorlayer.selectedFeatures()
        fieldclasses = set()
        for feature in selection:
            value = feature[selected_field_index]  # does this work?
            fieldclasses.add(str(value))
        QgsMessageLog.logMessage(f"all classes from field: {sorted(list(fieldclasses))}", "feature_annotator")
        vectorlayer.removeSelection()

        for c in fieldclasses:
            self.classes.add(str(c))
        self.populate_class_lists()

    def parse_feature(self):
        """
        Retrieve the value of the current feature at the selected field and display value in GUI, move the canvas to the extent of the feature.
        """
        # QgsMessageLog.logMessage(f"calling setup labeling", "feature_annotator")
        self.labeling_started = True
        vectorlayers = self.get_vectorlayers()
        vectorlayer = vectorlayers[self.dlg.sourcelayercbox.currentIndex()]
        vectorlayer.selectAll()
        selection = vectorlayer.selectedFeatures()

        # set correct feature index, as Qgis indices are 1-indexed i'll Add one
        self.dlg.featureindex.setText(str(self.feature_index + 1))
        QgsMessageLog.logMessage(f"feature index {self.feature_index}", "feature_annotator")

        selected_field_index = self.dlg.selectedannname.currentIndex()
        # set correct class label

        for i, feature in enumerate(selection):
            if i == self.feature_index:
                value = feature[selected_field_index]
                idx = sorted(list(self.classes)).index(str(value))
                QgsMessageLog.logMessage(f"all classes: {sorted(list(self.classes))}, idx of class: {idx}", "feature_annotator")
                self.dlg.annotationcbox.setCurrentIndex(idx)
                QgsMessageLog.logMessage(f"value of feature at field {selected_field_index}: {value}", "feature_annotator")

                # set map extent to polygon
                bbox = feature.geometry().boundingBox()
                xmax = bbox.xMaximum()
                ymax = bbox.yMaximum()
                ymin = bbox.yMinimum()
                xmin = bbox.xMinimum()
                QgsMessageLog.logMessage(f"bbox: {xmin}, {ymin}, {xmax}, {ymax}", "feature_annotator")
                # TODO: zoom out a little from the polygon so you can see context better.
                extent = QgsRectangle(xmin, ymin, xmax, ymax)
                vectorlayer.removeSelection()
                vectorlayer.select(self.feature_index)
                self.canvas.setExtent(extent)
                self.canvas.refresh()
                break

    def next_feature(self):
        """
        Change GUI values and canvas extent to the feature at the next index (if index exists).
        """
        if not self.labeling_started:
            return

        vectorlayers = self.get_vectorlayers()
        vectorlayer = vectorlayers[self.dlg.sourcelayercbox.currentIndex()]
        vectorlayer.selectAll()
        selection = vectorlayer.selectedFeatures()
        QgsMessageLog.logMessage(f"n features: {len(selection)}", "feature_annotator")
        if self.feature_index < len(selection) - 1:
            self.feature_index += 1
        vectorlayer.removeSelection()
        self.parse_feature()

    def prev_item(self):
        """
        Change GUI values and canvas extent to the feature at the previous index (if index exists).
        """
        if not self.labeling_started:
            return

        if self.feature_index > 0:
            self.feature_index -= 1
        self.parse_feature()

    def goto_index(self):
        """
        Change GUI values and canvas extent to the feature at the given index (if index exists).
        """
        if not self.labeling_started:
            return

        vectorlayers = self.get_vectorlayers()
        vectorlayer = vectorlayers[self.dlg.sourcelayercbox.currentIndex()]
        vectorlayer.selectAll()
        selection = vectorlayer.selectedFeatures()
        n_feats = len(selection)
        vectorlayer.removeSelection()
        target_index = int(self.dlg.gotoindexlineedit.displayText())

        if (target_index < n_feats - 1) & (target_index > 0):
            self.feature_index = target_index - 1
            self.parse_feature()

    def clear_classes(self):
        """
        Clear classes list.
        """
        self.classes = set()
        self.populate_class_lists()

    def update_attr_table(self):
        """
        Update the value/attribute of at the selected index with the value from the GUI.
        """
        # check if labeling phase has been started
        if not self.labeling_started:
            return

        vectorlayers = self.get_vectorlayers()
        vectorlayer = vectorlayers[self.dlg.sourcelayercbox.currentIndex()]
        selected_class = self.dlg.annotationcbox.currentText()
        selected_field_index = self.dlg.selectedannname.currentIndex()
        vectorlayer.dataProvider().changeAttributeValues({self.feature_index: {selected_field_index: selected_class}})
        QgsMessageLog.logMessage(f"changed attr at feature index {self.feature_index} to: {selected_class} in field {selected_field_index}", "feature_annotator")

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            # connect all buttons
            self.dlg.addlabeltype.clicked.connect(self.add_class)
            self.dlg.addanntype.clicked.connect(self.add_field)
            self.dlg.sourcelayercbox.currentIndexChanged.connect(self.source_select)
            self.dlg.retrieveclasses.clicked.connect(self.get_classes_from_field)
            self.dlg.startlabeling.clicked.connect(self.parse_feature)
            self.dlg.nextbutton.clicked.connect(self.next_feature)
            self.dlg.prevbutton.clicked.connect(self.prev_item)
            self.dlg.annotationcbox.currentIndexChanged.connect(self.update_attr_table)
            self.dlg.gotoindexbutton.clicked.connect(self.goto_index)
            self.dlg.emptyclasslist.clicked.connect(self.clear_classes)

            # self.dlg.annotationcbox

        # add vectorlayers
        self.populate_sourcelayercbox()
        self.dlg.featurenameinput.clear()
        self.dlg.labelinput.clear()
        self.dlg.gotoindexlineedit.clear()
        self.dlg.classlist.clear()
        self.dlg.featureindex.clear()
        self.dlg.annotationcbox.clear()
        self.dlg.default_feat_value.clear()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
