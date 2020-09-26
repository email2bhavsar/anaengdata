# This file is a part of Lector, a Qt based ebook reader
# Copyright (C) 2017-2019 BasioMeusPuga

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TODO
# Reading modes
# Double page, Continuous etc

import os
import logging

from PyQt5 import QtWidgets, QtGui, QtCore

from lector.sorter import resize_image
from lector.dockwidgets import PliantDockWidget, PliantNavBarWidget
from lector.contentwidgets import PliantQGraphicsView, PliantQTextBrowser

logger = logging.getLogger(__name__)


class Tab(QtWidgets.QWidget):
    def __init__(self, metadata, main_window, parent=None):
        super(Tab, self).__init__(parent)
        self._translate = QtCore.QCoreApplication.translate

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.main_window = main_window
        self.metadata = metadata  # Save progress data into this dictionary
        self.are_we_doing_images_only = self.metadata['images_only']
        self.is_fullscreen = False
        self.is_library = False

        self.masterLayout = QtWidgets.QHBoxLayout(self)
        self.masterLayout.setContentsMargins(0, 0, 0, 0)

        self.metadata['last_accessed'] = QtCore.QDateTime().currentDateTime()

        # Create relevant containers
        if not self.metadata['annotations']:
            self.metadata['annotations'] = {}
        if not self.metadata['bookmarks']:
            self.metadata['bookmarks'] = {}

        # Generate toc Model
        self.tocModel = QtGui.QStandardItemModel()
        self.tocModel.setHorizontalHeaderLabels(('Table of Contents',))
        self.generate_toc_model()

        # Get the current position of the book
        if self.metadata['position']:
            # A book might have been marked read without being opened
            if self.metadata['position']['is_read']:
                self.generate_position(True)
            current_chapter = self.metadata['position']['current_chapter']
        else:
            self.generate_position()
            current_chapter = 1

        # The content display widget is, by default a QTextBrowser.
        # In case the incoming data is only images
        # such as in the case of comic book files,
        # we want a QGraphicsView widget doing all the heavy lifting
        # instead of a QTextBrowser

        if self.are_we_doing_images_only:
            self.contentView = PliantQGraphicsView(
                self.metadata['path'], self.main_window, self)
            self.image_rotation = 0

        else:
            self.contentView = PliantQTextBrowser(
                self.main_window, self)
            self.contentView.setReadOnly(True)

            # TODO
            # Change this when HTML navigation works
            self.contentView.setOpenLinks(False)

            # TODO
            # Rename the .css files to something else here and keep
            # a record of them .Currently, I'm just removing them
            # for the sake of simplicity
            relative_path_root = os.path.join(
                self.main_window.temp_dir.path(), self.metadata['hash'])
            relative_paths = []
            for i in os.walk(relative_path_root):
                for j in i[2]:
                    file_extension = os.path.splitext(j)[1]
                    if file_extension == '.css':
                        file_path = os.path.join(i[0], j)
                        os.remove(file_path)
                relative_paths.append(os.path.join(relative_path_root, i[0]))
            self.contentView.setSearchPaths(relative_paths)

            self.hiddenButton = QtWidgets.QToolButton(self)
            self.hiddenButton.setVisible(False)
            self.hiddenButton.clicked.connect(self.set_cursor_position)

        # All content must be set through this function
        self.set_content(current_chapter, True, False)
        if not self.are_we_doing_images_only:
            # Setting this later breaks cursor positioning for search results
            self.hiddenButton.animateClick(50)

        # Load annotations for current content
        self.contentView.common_functions.load_annotations(current_chapter)

        # The following are common to both the text browser and
        # the graphics view
        self.contentView.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.contentView.setObjectName('contentView')
        self.contentView.verticalScrollBar().setSingleStep(
            self.main_window.settings['scroll_speed'])

        if self.main_window.settings['hide_scrollbars']:
            self.contentView.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff)
            self.contentView.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff)
        else:
            self.contentView.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarAsNeeded)
            self.contentView.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarAsNeeded)

        # Create a NavBar widget
        if self.main_window.settings['nav_bar']:
            self.navBar = PliantNavBarWidget(
                self.main_window, self.contentView, self)
            self.navBar.setFloating(True)
            self.navBar.setTitleBarWidget(QtWidgets.QWidget(self))
            self.navBar.hide()
        else:
            # This keeps from having to set visibility conditions
            # everywhere
            self.navBar = QtWidgets.QWidget()
            self.navBar.setFixedSize(0, 0)

        # Create a common dock for bookmarks, annotations, and search
        self.sideDock = PliantDockWidget(
            self.main_window, False, self.contentView, self)
        self.sideDock.populate()

        # Create the annotation notes dock
        self.annotationNoteDock = PliantDockWidget(
            self.main_window, True, self.contentView, self)
        self.annotationNoteDock.setWindowTitle(self._translate('Tab', 'Note'))
        self.annotationNoteDock.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable)
        self.annotationNoteDock.hide()

        self.annotationNoteEdit = QtWidgets.QTextEdit(self.annotationNoteDock)
        self.annotationNoteEdit.setMaximumSize(QtCore.QSize(250, 250))
        self.annotationNoteEdit.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.annotationNoteDock.setWidget(self.annotationNoteEdit)

        self.generate_keyboard_shortcuts()

        self.masterLayout.addWidget(self.contentView)
        self.masterLayout.addWidget(self.sideDock)
        self.masterLayout.addWidget(self.annotationNoteDock)

        # The following has to be after the docks are added to the layout
        self.sideDock.setFloating(True)
        self.sideDock.setWindowOpacity(.95)
        self.annotationNoteDock.setFloating(True)
        self.annotationNoteDock.setWindowOpacity(.95)
        self.sideDock.hide()

        # Create tab in the central tab widget
        title = self.metadata['title']
        if self.main_window.settings['attenuate_titles'] and len(title) > 30:
            title = title[:30] + '...'
        self.main_window.tabWidget.addTab(self, title)

        this_tab_index = self.main_window.tabWidget.indexOf(self)
        cover_icon = QtGui.QPixmap()
        cover_icon.loadFromData(self.metadata['cover'])
        self.main_window.tabWidget.setTabIcon(
            this_tab_index, QtGui.QIcon(cover_icon))

        # Hide mouse cursor timer
        self.mouseHideTimer = QtCore.QTimer()
        self.mouseHideTimer.setSingleShot(True)
        self.mouseHideTimer.timeout.connect(self.hide_mouse)

        # Hide the tab bar in case distraction free mode is active
        if not self.main_window.settings['show_bars']:
            self.main_window.tabWidget.tabBar().setVisible(False)

        self.contentView.setFocus()

    def toggle_side_dock(self, tab_required, override_hide=False):
        if (self.sideDock.isVisible()
                and self.sideDock.sideDockTabWidget.currentIndex() == tab_required
                and not override_hide):
            self.sideDock.hide()
        elif not self.sideDock.isVisible():
            self.sideDock.show()
            if tab_required == 2:
                self.sideDock.activateWindow()
                self.sideDock.search.searchLineEdit.setFocus()
                self.sideDock.search.searchLineEdit.selectAll()

        self.sideDock.sideDockTabWidget.setCurrentIndex(tab_required)

    def generate_rotation(self, delta_angle):
        self.image_rotation += delta_angle

        # Set bounds for rotation angle
        if self.image_rotation == 360:
            self.image_rotation = 0
        if self.image_rotation == -90:
            self.image_rotation = 270

    def update_last_accessed_time(self):
        self.metadata['last_accessed'] = QtCore.QDateTime().currentDateTime()

        start_index = self.main_window.lib_ref.libraryModel.index(0, 0)
        matching_item = self.main_window.lib_ref.libraryModel.match(
            start_index,
            QtCore.Qt.UserRole + 6,
            self.metadata['hash'],
            1, QtCore.Qt.MatchExactly)

        try:
            self.main_window.lib_ref.libraryModel.setData(
                matching_item[0],
                self.metadata['last_accessed'], QtCore.Qt.UserRole + 12)
        except IndexError:  # The file has been deleted
            pass

    def set_cursor_position(self, cursor_position=None, select_chars=0):
        try:
            required_position = self.metadata['position']['cursor_position']
        except KeyError:
            logging.error('Database: Cursor position error. Recommend retry.')
            return

        if cursor_position:
            required_position = cursor_position

        # This is needed so that the line we want is
        # always at the top of the window
        self.contentView.verticalScrollBar().setValue(
            self.contentView.verticalScrollBar().maximum())

        # textCursor() RETURNS a copy of the textcursor
        cursor = self.contentView.textCursor()
        cursor.setPosition(
            required_position - select_chars,
            QtGui.QTextCursor.MoveAnchor)
        if select_chars > 0:  # Select search results
            cursor.movePosition(
                QtGui.QTextCursor.NextCharacter,
                QtGui.QTextCursor.KeepAnchor,
                select_chars)
        self.contentView.setTextCursor(cursor)
        self.contentView.ensureCursorVisible()

        # Finally, to make sure the cover image isn't
        # scrolled halfway through on first open,
        if self.metadata['cover'] and self.metadata['position']['current_chapter'] == 1:
            self.contentView.verticalScrollBar().setValue(0)

    def generate_position(self, is_read=False):
        total_chapters = len(self.metadata['content'])

        current_chapter = 1
        if is_read:
            current_chapter = total_chapters

        # Generate block count @ time of first read
        # Blocks are indexed from 0 up
        blocks_per_chapter = []
        total_blocks = 0

        if not self.are_we_doing_images_only:
            for i in self.metadata['content']:
                textDocument = QtGui.QTextDocument(None)
                textDocument.setHtml(i)
                block_count = textDocument.blockCount()

                blocks_per_chapter.append(block_count)
                total_blocks += block_count

        self.metadata['position'] = {
            'current_chapter': current_chapter,
            'total_chapters': total_chapters,
            'blocks_per_chapter': blocks_per_chapter,
            'total_blocks': total_blocks,
            'is_read': is_read,
            'current_block': 0,
            'cursor_position': 0}

    def generate_keyboard_shortcuts(self):
        ksNextChapter = QtWidgets.QShortcut(
            QtGui.QKeySequence('Right'), self.contentView)
        ksNextChapter.setObjectName('nextChapter')
        ksNextChapter.activated.connect(self.sneaky_change)

        ksPrevChapter = QtWidgets.QShortcut(
            QtGui.QKeySequence('Left'), self.contentView)
        ksPrevChapter.setObjectName('prevChapter')
        ksPrevChapter.activated.connect(self.sneaky_change)

        ksGoFullscreen = QtWidgets.QShortcut(
            QtGui.QKeySequence('F'), self.contentView)
        ksGoFullscreen.activated.connect(self.go_fullscreen)

        ksExitFullscreen = QtWidgets.QShortcut(
            QtGui.QKeySequence('Escape'), self.contentView)
        ksExitFullscreen.setContext(QtCore.Qt.ApplicationShortcut)
        ksExitFullscreen.activated.connect(self.exit_fullscreen)

        ksToggleBookmarks = QtWidgets.QShortcut(
            QtGui.QKeySequence('Ctrl+B'), self.contentView)
        ksToggleBookmarks.activated.connect(
            lambda: self.toggle_side_dock(0))

        # Shortcuts not required for comic view functionality
        if not self.are_we_doing_images_only:
            ksToggleAnnotations = QtWidgets.QShortcut(
                QtGui.QKeySequence('Ctrl+N'), self.contentView)
            ksToggleAnnotations.activated.connect(
                lambda: self.toggle_side_dock(1))

            ksToggleSearch = QtWidgets.QShortcut(
                QtGui.QKeySequence('Ctrl+F'), self.contentView)
            ksToggleSearch.activated.connect(
                lambda: self.toggle_side_dock(2))

    def generate_toc_model(self):
        # The toc list is:
        # 0: Level
        # 1: Title
        # 2: Chapter content / page number
        # pprint it out to get a better idea of structure

        toc = self.metadata['toc']
        parent_list = []
        for i in toc:
            item = QtGui.QStandardItem()
            item.setText(i[1])
            item.setData(i[2], QtCore.Qt.UserRole)
            item.setData(i[1], QtCore.Qt.UserRole + 1)

            current_level = i[0]
            if current_level == 1:
                self.tocModel.appendRow(item)
                parent_list.clear()
                parent_list.append(item)
            else:
                parent_list[current_level - 2].appendRow(item)
                try:
                    next_level = toc[toc.index(i) + 1][0]
                    if next_level > current_level:
                        parent_list.append(item)

                    if next_level < current_level:
                        level_difference = current_level - next_level
                        parent_list = parent_list[:-level_difference]
                except IndexError:
                    pass

        # This is needed to be able to have the toc Combobox
        # jump to the correct position in the book when it is
        # first opened
        self.main_window.bookToolBar.tocBox.setModel(self.tocModel)
        self.main_window.bookToolBar.tocTreeView.expandAll()

    def go_fullscreen(self):
        # To allow toggles to function
        # properly after the fullscreening

        self.sideDock.hide()
        self.annotationNoteDock.hide()

        if self.contentView.windowState() == QtCore.Qt.WindowFullScreen:
            self.exit_fullscreen()
            return

        if not self.are_we_doing_images_only:
            self.contentView.record_position()

        self.contentView.setWindowFlags(QtCore.Qt.Window)
        self.contentView.setWindowState(QtCore.Qt.WindowFullScreen)
        self.contentView.show()
        self.main_window.hide()

        if not self.are_we_doing_images_only:
            self.hiddenButton.animateClick(50)

        self.mouseHideTimer.start(2000)
        self.is_fullscreen = True

    def exit_fullscreen(self):
        # Intercept escape presses
        for i in (self.annotationNoteDock, self.sideDock):
            if i.isVisible():
                i.setVisible(False)
                return

        # Prevents cursor position change on escape presses
        if self.main_window.isVisible():
            return

        if not self.are_we_doing_images_only:
            self.contentView.record_position()

        self.main_window.show()
        self.contentView.setWindowFlags(QtCore.Qt.Widget)
        self.contentView.setWindowState(QtCore.Qt.WindowNoState)
        self.contentView.show()
        self.is_fullscreen = False

        if not self.are_we_doing_images_only:
            self.hiddenButton.animateClick(100)

        # Hide the view modification buttons in case they're visible
        self.main_window.bookToolBar.customize_view_off()

        # Exit distraction free mode too
        if not self.main_window.settings['show_bars']:
            self.main_window.toggle_distraction_free()

        self.navBar.hide()
        self.mouseHideTimer.start(2000)
        self.contentView.setFocus()

    def set_content(self, required_position, tocBox_readjust=False, record_position=False):
        # All content changes must come through here
        # This function will decide how to relate
        # entries in the toc to the actual content

        # Set the required page to the corresponding index
        # For images this is simply a page number
        # For text based books, this is the entire text of the chapter
        try:
            required_content = self.metadata['content'][required_position - 1]
        except IndexError:
            return  # Do not allow cycling beyond last page

        # Update the metadata dictionary to save position
        self.metadata['position']['current_chapter'] = required_position
        self.metadata['position']['is_read'] = False
        if record_position:
            self.contentView.record_position()

        if self.are_we_doing_images_only:
            self.contentView.loadImage(required_content)
        else:
            self.contentView.clear()
            self.contentView.setHtml(required_content)

        # Set the contentview to look the way God intended
        self.main_window.profile_functions.format_contentView()
        self.contentView.common_functions.load_annotations(required_position)

        # Change the index of the tocBox. This is manual and each function
        # that calls set_position must specify if it needs this adjustment
        if tocBox_readjust:
            self.set_tocBox_index(required_position, None)

            # The NavBar doesn't get declared until later
            try:
                self.set_tocBox_index(
                    required_position, self.navBar.tocComboBox)
            except AttributeError:
                pass

        self.contentView.setFocus()

    def set_tocBox_index(self, current_position=None, tocBox=None):
        # Get current position from the metadata dictionary
        # in case it isn't specified
        if not current_position:
            current_position = self.metadata['position']['current_chapter']

        position_reference = 1
        for i in reversed(self.metadata['toc']):
            if i[2] <= current_position:
                position_reference = i[2]
                break

        # Match the position reference to the corresponding
        # index in the QTreeView / QCombobox
        try:
            matchingIndex = self.tocModel.match(
                self.tocModel.index(0, 0),
                QtCore.Qt.UserRole,
                position_reference,
                2, QtCore.Qt.MatchRecursive)[0]
        except IndexError:
            return

        # A tocBox name is specified for the context menu
        if not tocBox:
            tocBox = self.main_window.bookToolBar.tocBox

        # The following sets the QCombobox index according
        # to the index found above.
        tocBox.blockSignals(True)
        currentRootModelIndex = tocBox.rootModelIndex()
        tocBox.setRootModelIndex(matchingIndex.parent())
        tocBox.setCurrentIndex(matchingIndex.row())
        tocBox.setRootModelIndex(currentRootModelIndex)
        tocBox.blockSignals(False)

    def format_view(
            self, font, font_size, foreground,
            background, padding, line_spacing,
            text_alignment):

        if self.are_we_doing_images_only:
            # Tab color does not need to be set separately in case
            # no padding is set for the viewport of a QGraphicsView
            # and image resizing in done in the pixmap
            my_qbrush = QtGui.QBrush(QtCore.Qt.SolidPattern)
            my_qbrush.setColor(background)
            self.contentView.setBackgroundBrush(my_qbrush)
            self.contentView.resizeEvent()

        else:
            self.contentView.setStyleSheet(
                "QTextEdit {{font-family: {0}; font-size: {1}px; color: {2}; background-color: {3}}}".format(
                    font, font_size, foreground.name(), background.name()))

            # Line spacing
            # Set line spacing per a block format
            # This is proportional line spacing so assume a divisor of 100
            block_format = QtGui.QTextBlockFormat()
            block_format.setLineHeight(
                line_spacing, QtGui.QTextBlockFormat.ProportionalHeight)

            block_format.setTextIndent(50)

            # Give options for alignment
            alignment_dict = {
                'left': QtCore.Qt.AlignLeft,
                'right': QtCore.Qt.AlignRight,
                'center': QtCore.Qt.AlignCenter,
                'justify': QtCore.Qt.AlignJustify}

            # Also for padding
            # Using setViewPortMargins for this disables scrolling in the margins
            block_format.setLeftMargin(padding)
            block_format.setRightMargin(padding)

            this_cursor = self.contentView.textCursor()
            this_cursor.setPosition(QtGui.QTextCursor.Start)

            while True:
                # So this fixes the stupid repetitive iteration
                # I was doing over the entire thing
                # It also allows for all images to be center aligned.
                # Magic. *jazz hands*
                block_text = this_cursor.block().text().strip()
                try:
                    # Object replacement char - Seems to work with images
                    if ord(block_text) == 65532:
                        block_format.setAlignment(
                            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignHCenter)
                    else:
                        raise TypeError
                except TypeError:
                    block_format.setAlignment(alignment_dict[text_alignment])

                # Iterate over the entire document block by block
                # The document ends when the cursor position can no longer be incremented
                old_position = this_cursor.position()
                this_cursor.mergeBlockFormat(block_format)
                this_cursor.movePosition(
                    QtGui.QTextCursor.NextBlock, QtGui.QTextCursor.MoveAnchor)

                new_position = this_cursor.position()
                if old_position == new_position:
                    break

    def hide_mouse(self):
        self.contentView.viewport().setCursor(QtCore.Qt.BlankCursor)

        if self.contentView.hasFocus():
            self.navBar.hide()

    def sneaky_change(self):
        direction = -1
        if self.sender().objectName() == 'nextChapter':
            direction = 1

        self.contentView.common_functions.change_chapter(
            direction, True)

    def sneaky_exit(self):
        self.contentView.hide()
        self.main_window.closeEvent()


class PliantQGraphicsScene(QtWidgets.QGraphicsScene):
    def __init__(self, parent=None):
        super(PliantQGraphicsScene, self).__init__(parent)
        self.parent = parent
        self._translate = QtCore.QCoreApplication.translate

    def mouseReleaseEvent(self, event):
        self.parent.previous_position = self.parent.pos()

        image_files = '*.jpg *.png'
        dialog_prompt = self._translate('PliantQGraphicsScene', 'Select new cover')
        images_string = self._translate('PliantQGraphicsScene', 'Images')
        new_cover = QtWidgets.QFileDialog.getOpenFileName(
            None, dialog_prompt, self.parent.parent.settings['last_open_path'],
            f'{images_string} ({image_files})')[0]

        if not new_cover:
            self.parent.show()
            return

        with open(new_cover, 'rb') as cover_ref:
            cover_bytes = cover_ref.read()
            resized_cover = resize_image(cover_bytes)
            self.parent.cover_for_database = resized_cover

        cover_pixmap = QtGui.QPixmap()
        cover_pixmap.load(new_cover)
        cover_pixmap = cover_pixmap.scaled(
            140, 205, QtCore.Qt.IgnoreAspectRatio)

        self.parent.load_cover(cover_pixmap, True)
        self.parent.show()


class DragDropListView(QtWidgets.QListView):
    # This is the library listview
    def __init__(self, main_window, parent):
        super(DragDropListView, self).__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setResizeMode(QtWidgets.QListView.Fixed)
        self.setLayoutMode(QtWidgets.QListView.SinglePass)
        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setProperty("showDropIndicator", False)
        self.setProperty("isWrapping", True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setObjectName("listView")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super(DragDropListView, self).dragEnterEvent(event)

    def dragMoveEvent(self, event):
        super(DragDropListView, self).dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            file_list = [url.path() for url in event.mimeData().urls()]
            self.main_window.process_post_hoc_files(file_list, False)
            event.acceptProposedAction()
        else:
            super(DragDropListView, self).dropEvent(event)


class DragDropTableView(QtWidgets.QTableView):
    # This is the library tableview
    def __init__(self, main_window, parent):
        super(DragDropTableView, self).__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setFrameShape(QtWidgets.QFrame.Box)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setSizeAdjustPolicy(
            QtWidgets.QAbstractScrollArea.AdjustToContentsOnFirstShow)
        self.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked |
            QtWidgets.QAbstractItemView.EditKeyPressed |
            QtWidgets.QAbstractItemView.SelectedClicked)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setGridStyle(QtCore.Qt.NoPen)
        self.setSortingEnabled(True)
        self.setWordWrap(False)
        self.setObjectName("tableView")
        self.horizontalHeader().setVisible(True)
        self.verticalHeader().setVisible(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super(DragDropTableView, self).dragEnterEvent(event)

    def dragMoveEvent(self, event):
        super(DragDropTableView, self).dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            file_list = [url.path() for url in event.mimeData().urls()]
            self.main_window.process_post_hoc_files(file_list, False)
            event.acceptProposedAction()
        else:
            super(DragDropTableView, self).dropEvent(event)


class SaysHelloWhenClicked(QtWidgets.QListView):
    # Signal declarations must be outside the constructor
    # The argument is the type of the data emitted
    newIndexSignal = QtCore.pyqtSignal(QtCore.QModelIndex)

    def __init__(self, parent):
        super(SaysHelloWhenClicked, self).__init__(parent)
        self.parent = parent

    def currentChanged(self, index, previous_index):
        if not index.isValid():
            return

        self.newIndexSignal.emit(index)
