// Control Window — lives on Display 1.
// All user interaction happens here. Never touches the mirror directly.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

import "components"

ApplicationWindow {
    id: controlWindow
    objectName: "controlWindow"

    // Hidden initially; screen_manager will call showFullScreen()
    visible: false
    width: 1280
    height: 800
    title: "Smart Mirror Pi"
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "#f2ece7"

    // ── Global keyboard shortcuts ─────────────────────────────────────
    Shortcut { sequence: "Ctrl+Q"; onActivated: Qt.quit() }

    // ── Navigation locked while recording ────────────────────────────
    readonly property bool navLocked:
        recordingController ? (recordingController.isRecording
            || recordingController.hasReview
            || recordingController.countdown > 0) : false

    // ── Side navigation strip — defined first so content can anchor to it ──
    Rectangle {
        id: navStrip
        anchors { left: parent.left; top: parent.top; bottom: statusBar.top }
        width: appController && appController.currentPage === "login" ? 0 : 72
        visible: width > 0
        color: "#e8e0d9"
        z: 2

        Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutQuad } }

        ColumnLayout {
            anchors { fill: parent; topMargin: 16; bottomMargin: 16 }
            spacing: 6

            Repeater {
                model: [
                    { icon: "⌂", page: "dashboard",  tip: "Home" },
                    { icon: "⏺", page: "recording",  tip: "Record" },
                    { icon: "▦", page: "gallery",    tip: "Gallery" },
                    { icon: "⚙", page: "settings",   tip: "Settings" },
                ]

                Rectangle {
                    width: 56; height: 56; radius: 14
                    Layout.alignment: Qt.AlignHCenter
                    color: appController && appController.currentPage === modelData.page
                           ? "#d0c8c0" : "transparent"
                    border.width: appController && appController.currentPage === modelData.page ? 1 : 0
                    border.color: "#c4b8ac"

                    Text {
                        anchors.centerIn: parent
                        text: modelData.icon
                        font.pixelSize: 24
                        color: appController && appController.currentPage === modelData.page
                               ? "#3c3530" : "#9d9590"
                    }

                    ToolTip.visible: navMa.containsMouse
                    ToolTip.text: modelData.tip
                    ToolTip.delay: 600

                    MouseArea {
                        id: navMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: !controlWindow.navLocked || modelData.page === "recording"
                        onClicked: {
                            if (!appController) return
                            switch (modelData.page) {
                                case "dashboard": appController.showDashboard(); break
                                case "recording": appController.showRecording(); break
                                case "gallery":
                                    if (galleryController) galleryController.refresh()
                                    appController.showGallery()
                                    break
                                case "settings":  appController.showSettings(); break
                            }
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // Mirror status dot
            Rectangle {
                width: 12; height: 12; radius: 999
                Layout.alignment: Qt.AlignHCenter
                color: mirrorDisplay && mirrorDisplay.mode !== "idle" ? "#5a9a6a" : "#c4b8ac"
                ToolTip.visible: dotMa.containsMouse
                ToolTip.text: "Mirror: " + (mirrorDisplay ? mirrorDisplay.mode : "—")
                MouseArea { id: dotMa; anchors.fill: parent; hoverEnabled: true }
            }
        }
    }

    // ── Status / error bar ───────────────────────────────────────────
    StatusBar {
        id: statusBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        statusText: appController ? appController.statusMessage : ""
        errorText:  appController ? appController.errorMessage  : ""
    }

    // ── Page content area (right of nav strip, above status bar) ─────
    Item {
        id: content
        anchors {
            top: parent.top
            left: navStrip.right
            right: parent.right
            bottom: statusBar.top
        }

        // Warm gradient background
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#f4ede8" }
                GradientStop { position: 1.0; color: "#ece5df" }
            }
        }

        // Page loader
        Loader {
            id: pageLoader
            anchors.fill: parent
            source: appController ? _pageQml(appController.currentPage) : ""

            function _pageQml(page) {
                switch (page) {
                    case "login":        return "pages/LoginPage.qml"
                    case "dashboard":    return "pages/DashboardPage.qml"
                    case "recording":    return "pages/RecordingPage.qml"
                    case "gallery":      return "pages/GalleryPage.qml"
                    case "player":       return "pages/PlayerPage.qml"
                    case "compare":      return "pages/ComparePage.qml"
                    case "live_compare": return "pages/LiveComparePage.qml"
                    case "settings":     return "pages/SettingsPage.qml"
                    case "export":       return "pages/ExportPage.qml"
                    default:             return "pages/DashboardPage.qml"
                }
            }

            onStatusChanged: {
                if (status === Loader.Error)
                    console.error("PageLoader failed to load:", source)
            }
        }
    }
}
