// Control Window — lives on Display 1.
// All user interaction happens here. Never touches the mirror directly.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

import "components"
import "pages"

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

    // ── Navigation locked while recording ────────────────────────────
    readonly property bool navLocked:
        recordingController.isRecording
        || recordingController.hasReview
        || recordingController.countdown > 0

    // ── Page switcher ────────────────────────────────────────────────
    Item {
        id: content
        anchors { top: parent.top; left: navStrip.right; right: parent.right; bottom: statusBar.top }

        // Gradient background
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#f4ede8" }
                GradientStop { position: 1.0; color: "#ece5df" }
            }
        }

        Loader {
            id: pageLoader
            anchors.fill: parent
            source: _pageSource(appController.currentPage)

            function _pageSource(page) {
                switch (page) {
                    case "dashboard":    return "pages/DashboardPage.qml"
                    case "recording":    return "pages/RecordingPage.qml"
                    case "gallery":      return "pages/GalleryPage.qml"
                    case "player":       return "pages/PlayerPage.qml"
                    case "compare":      return "pages/ComparePage.qml"
                    case "live_compare": return "pages/LiveComparePage.qml"
                    case "settings":     return "pages/SettingsPage.qml"
                    default:             return "pages/DashboardPage.qml"
                }
            }

            // Fade transition between pages
            Behavior on source {
                SequentialAnimation {
                    NumberAnimation { target: pageLoader; property: "opacity"; to: 0; duration: 100 }
                    PropertyAction  { }
                    NumberAnimation { target: pageLoader; property: "opacity"; to: 1; duration: 160 }
                }
            }
        }
    }

    // ── Status / error bar ───────────────────────────────────────────
    StatusBar {
        id: statusBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        statusText: appController.statusMessage
        errorText: appController.errorMessage
    }

    // ── Side navigation strip (compact) ─────────────────────────────
    Rectangle {
        id: navStrip
        anchors { left: parent.left; top: parent.top; bottom: statusBar.top }
        width: 52
        color: "#e8e0d9"
        border.width: 0

        ColumnLayout {
            anchors { fill: parent; topMargin: 16; bottomMargin: 16 }
            spacing: 4

            Repeater {
                model: [
                    { icon: "⌂", page: "dashboard",  tip: "Home" },
                    { icon: "⏺", page: "recording",  tip: "Record" },
                    { icon: "▦", page: "gallery",    tip: "Gallery" },
                    { icon: "⚙", page: "settings",   tip: "Settings" },
                ]

                Rectangle {
                    width: 40; height: 40
                    radius: 10
                    Layout.alignment: Qt.AlignHCenter
                    color: appController.currentPage === modelData.page
                           ? "#d0c8c0" : "transparent"
                    border.width: appController.currentPage === modelData.page ? 1 : 0
                    border.color: "#c4b8ac"

                    Text {
                        anchors.centerIn: parent
                        text: modelData.icon
                        font.pixelSize: 18
                        color: appController.currentPage === modelData.page
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
                            switch (modelData.page) {
                                case "dashboard": appController.showDashboard(); break
                                case "recording": appController.showRecording(); break
                                case "gallery":   galleryController.refresh(); appController.showGallery(); break
                                case "settings":  appController.showSettings(); break
                            }
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // Mirror status dot
            Rectangle {
                width: 12; height: 12
                radius: 999
                Layout.alignment: Qt.AlignHCenter
                color: mirrorDisplay.mode === "idle" ? "#c4b8ac" : "#5a9a6a"
                ToolTip.visible: dotMa.containsMouse
                ToolTip.text: "Mirror: " + mirrorDisplay.mode
                MouseArea { id: dotMa; anchors.fill: parent; hoverEnabled: true }
            }
        }
    }

}
