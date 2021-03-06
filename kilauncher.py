#!/usr/bin/python
# KiLauncher static fullscreen launcher menu
# By Alan D Moore
# Copyright 2012
# Released under the GNU GPL v3

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from xdg.DesktopEntry import DesktopEntry

import sys
import glob
import yaml
import os
import argparse

def recursive_find(rootdir, myfilename):
    return [os.path.join(rootdir, filename)
            for rootdir, dirnames, filenames in os.walk(rootdir)
            for filename in filenames
            if filename == myfilename]


def icon_anyway_you_can(icon_name, recursive_search=True):
    """Takes an icon name or path, and returns a QIcon any way it can"""
    icon = None
    if os.path.isfile(icon_name):
        icon = QIcon(icon_name)
    elif QIcon.hasThemeIcon(icon_name):
        icon = QIcon.fromTheme(icon_name)
    elif os.path.isfile(os.path.join("/usr/share/pixmaps", icon_name)):
        icon = QIcon(os.path.join("/usr/share/pixmaps", icon_name))
    elif recursive_search:
        #Last ditch effort
        #search through some known (Linux) icon locations
        #This recursive search is really slow, hopefully it can be avoided.
        print("Warning: had to recursively search for icon \"%s\".  Please set a full path to the correct file to reduce startup time." % icon_name)
        directories = ["/usr/share/pixmaps", "/usr/share/icons", "/usr/share/icons/hicolor", "/usr/share/" + icon_name]
        extensions = ["", ".png", ".xpm", ".svg", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".ico"]
        possible_filenames = [icon_name + extension for extension in extensions]
        for directory in directories:
            for filename in possible_filenames:
                paths = recursive_find(directory, filename)
                if paths:
                    print("(eventually found \"%s\")" % paths[0])
                    icon = QIcon(paths[0])
                    break
            if icon:
                break
        if not icon:
            print("Couldn't find an icon for \"%s\"" % icon_name)
    return icon or QIcon()



class LaunchButton(QPushButton):
    """This is the actual button you push to launch the program."""

    def __init__(self, parent=None, **kwargs):
        super(LaunchButton, self).__init__(parent)
        self.setObjectName("LaunchButton")
        self.launcher_size = kwargs.get("launcher_size")
        self.icon_size = kwargs.get("icon_size")
        self.name, self.comment, self.icon, self.command = None, None, None, None

        # Load in details from a .desktop file, if there is one.
        if kwargs.get("desktop_file"):
            de = DesktopEntry(kwargs.get("desktop_file"))
            self.name = de.getName()
            self.comment = de.getComment()
            self.icon = de.getIcon()
            self.command = de.getExec()

        # This allows for overriding the settings in DesktopEntry
        self.name = kwargs.get("name", self.name)
        self.comment = kwargs.get("comment", self.comment)
        self.icon = kwargs.get("icon", self.icon)
        self.command =  kwargs.get("command", self.command)

        # Create the layouts and widgets to hold the information
        toplayout = QHBoxLayout()
        leftlayout = QVBoxLayout()

        # The button's title
        title = QLabel(self.name)
        title.setObjectName("LaunchButtonTitle")
        leftlayout.addWidget(title)

        # The button's descriptive comment
        comment = QLabel(self.comment)
        comment.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        comment.setWordWrap(True)
        comment.setObjectName("LaunchButtonDescription")
        leftlayout.addWidget(comment)

        # The button's icon, if there is one
        iconpane = QLabel()
        icon = (self.icon and icon_anyway_you_can(self.icon, kwargs.get("aggressive_icon_search", False))) or QIcon()
        pixmap = icon.pixmap(*self.icon_size)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(*self.icon_size)
        iconpane.setPixmap(pixmap)

        # Add everything to layouts and layouts to the button
        toplayout.addWidget(iconpane)
        toplayout.addLayout(leftlayout)
        self.setLayout(toplayout)

        # Set the button's size from config.
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(*self.launcher_size))

        # Connect the callback
        self.connect(self, SIGNAL("clicked()"), self.callback)

    def enable(self, exit_code):
        self.setDisabled(False)

    def enable_with_error(self, error):
        self.setDisabled(False)
        QMessageBox.critical(None, "Command Failed!", "Sorry, this program isn't working!")

    def callback(self):
        # commands are called in a separate thread using QProcess.
        # This way, they can indicate to us when they are finished, or if they ran correctly, using signals
        # XDG commands in desktop files sometimes have placeholder arguments like '%u' or '%f'.
        # We're going to strip these out.
        self.command = ' '.join(x for x in self.command.split() if x not in ('%f', '%F', '%u', '%U'))
        self.p = QProcess()
        self.connect(self.p, SIGNAL("finished(int)"), self.enable)
        self.connect(self.p, SIGNAL("error(QProcess::ProcessError)"), self.enable_with_error)
        self.p.start(self.command)
        if not self.p.state == QProcess.NotRunning:
            # Disable the button to prevent users clicking 200 times waiting on a slow program.
            self.setDisabled(True)


class LauncherMenu(QWidget):
    """This is a single pane of launchers on a tab"""
    def __init__(self, config, parent=None):
        super(LauncherMenu, self).__init__(parent)
        self.config = config
        self.launcherlayout = QGridLayout()
        self.layout = QVBoxLayout()
        # Show the description
        self.descriptionLabel = QLabel(self.config.get("description"))
        self.descriptionLabel.setObjectName("TabDescription")
        self.layout.addWidget(self.descriptionLabel)
        self.scroller = QScrollArea()
        self.scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroller.setWidgetResizable(True)
        self.launcher_widget = QWidget(self)
        self.launcher_widget.setObjectName("LauncherPane")
        self.launcher_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.launcher_widget.setLayout(self.launcherlayout)
        self.layout.addWidget(self.scroller)
        self.setLayout(self.layout)
        self.launcher_size = (config.get("launcher_size") and [int(x) for x in config.get("launcher_size").split('x')]) or [240, 80]
        self.icon_size = (config.get("icon_size") and [int(x) for x in config.get("icon_size").split('x')]) or [64, 64]
        # figure out the default number of columns by dividing the launcher width by the screen width.
        # Of course, if that's zero (if the launcher is actually wider than the viewport) make it 1
        self.default_columns = (qApp.desktop().availableGeometry().width() // self.launcher_size[0]) or 1
        self.columns = config.get("launchers_per_row", self.default_columns)
        self.current_coordinates = [0, 0]
        if self.config.get("desktop_path"):
            self.add_launchers_from_path(self.config.get("desktop_path"))
        if self.config.get("launchers"):
            for launcher in self.config.get("launchers"):
                launcher["launcher_size"] = self.launcher_size
                launcher["icon_size"] = self.icon_size
                launcher["aggressive_icon_search"] = self.config.get("aggressive_icon_search", False)
                b = LaunchButton(**launcher)
                self.add_launcher_to_layout(b)
        self.scroller.setWidget(self.launcher_widget)

    def add_launchers_from_path(self, path):
        for desktop_file in glob.glob(path):
            b = LaunchButton(desktop_file=desktop_file, launcher_size=self.launcher_size, icon_size=self.icon_size, aggressive_icon_search=self.config.get("aggressive_icon_search"))
            self.add_launcher_to_layout(b)

    def add_launcher_to_layout(self, launcher):
        self.launcherlayout.addWidget(launcher, self.current_coordinates[0], self.current_coordinates[1])
        self.current_coordinates[1] += 1
        if self.current_coordinates[1] % self.columns == 0:
            self.current_coordinates[1] = 0
            self.current_coordinates[0] += 1

class KiLauncher(QTabWidget):
    """This is the main appliation"""

    def __init__(self, config, parent=None, **kwargs):
        super(KiLauncher, self).__init__(parent)
        self.setObjectName("KiLauncher")
        self.tabBar().setObjectName("TabBar")
        self.aggressive_icon_search = config.get("aggressive_icon_search")
        self.stylesheet = kwargs.get("stylesheet") or config.get("stylesheet", 'stylesheet.css')
        if not os.path.exists(self.stylesheet):
            print("Warning: stylesheet file %s could not be located.  Using default style." % self.stylesheet)
            self.stylesheet = None
        #Ideally, the menu should be full screen, but always stay beneath other windows
        self.setWindowState(Qt.WindowFullScreen)
        self.setWindowFlags(self.windowFlags()|Qt.WindowStaysOnBottomHint|Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_X11NetWmWindowTypeMenu, True)
        #"fullscreen" doesn't always work, depending on the WM.  This is a workaround.
        self.resize(qApp.desktop().availableGeometry().size())

        # Setup the appearance
        if self.stylesheet:
            self.setStyleSheet(open(self.stylesheet, 'r').read())
        if config.get("icon_theme"):
            QIcon.setThemeName(config.get("icon_theme"))

        # Set up the tabs
        self.tabs = config.get("tabs_and_launchers")
        if self.tabs:
            self.init_tabs()
        else:
            self.setLayout(QHBoxLayout())
            self.layout().addWidget(QLabel("No tabs were configured.  Please check your configuration file."))

        #Quit button
        if (config.get("show_quit_button")):
            self.quit_button = QPushButton(config.get("quit_button_text") or "X")
            self.quit_button.setObjectName("QuitButton")
            self.setCornerWidget(self.quit_button)
            self.connect(self.quit_button, SIGNAL("clicked()"), self.close)

        #Since tabs are not dynamic, just hide them if there's only one.
        self.tabBar().setVisible(len(self.tabs) > 1)

    def init_tabs(self):
        for tabordinal, launchers in sorted(self.tabs.items()):
            launchers["aggressive_icon_search"] = self.aggressive_icon_search
            lm = LauncherMenu(launchers)
            if launchers.get("icon"):
                icon = launchers.get("icon")
                icon = icon_anyway_you_can(icon, False)
                self.addTab(lm, icon, launchers.get("name"))
            else:
                self.addTab(lm, launchers.get("name"))

if __name__ == '__main__':
    config_locations = ['/etc/kilauncher.yaml', '~/.kilauncher.yaml']
    config_file = ''
    for config_location in config_locations:
        if os.path.exists(os.path.expanduser(config_location)):
            config_file = config_location
    app = QApplication(sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", action="store", dest="config", default=None, help="The configuration file to use.")
    parser.add_argument("-s", "--stylesheet", action="store", dest="stylesheet", default=None, help="Override the stylesheet in the config file.")
    args = parser.parse_args()
    config_file = args.config or os.path.expanduser(config_file)
    if not config_file:
        print("No config file found or specified; exiting")
        sys.exit(1)
    print(config_file)
    config = yaml.safe_load(open(config_file, 'r'))
    l = KiLauncher(config, stylesheet=args.stylesheet)
    l.show()
    app.exec_()
