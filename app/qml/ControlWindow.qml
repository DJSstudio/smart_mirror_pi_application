// Control Window — lives on Display 1.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

import "components"

ApplicationWindow {
    id: controlWindow
    objectName: "controlWindow"

    visible: false
    width: 1280
    height: 800
    title: "Smart Mirror Pi"
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "#F7F5F2"

    // ── Global shortcut ───────────────────────────────────────────────
    Shortcut { sequence: "Ctrl+Q"; onActivated: Qt.quit() }

    // ── Nav locked while recording ────────────────────────────────────
    readonly property bool navLocked:
        recordingController ? (recordingController.isRecording
            || recordingController.hasReview
            || recordingController.countdown > 0) : false

    // ── Side navigation strip ─────────────────────────────────────────
    Rectangle {
        id: navStrip
        anchors { left: parent.left; top: parent.top; bottom: statusBar.top }
        width: appController && appController.currentPage === "login" ? 0 : 88
        visible: width > 0
        color: "#1C1917"
        z: 2

        Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }

        ColumnLayout {
            anchors { fill: parent; topMargin: 20; bottomMargin: 16 }
            spacing: 2

            Repeater {
                model: [
                    { icon: "⌂",  page: "dashboard", label: "Home"     },
                    { icon: "⏺",  page: "recording",  label: "Record"   },
                    { icon: "▦",  page: "gallery",    label: "Looks"    },
                    { icon: "⚙",  page: "settings",   label: "Settings" },
                ]

                // Nav item: icon + label stacked
                Item {
                    Layout.fillWidth: true
                    height: 72

                    readonly property bool isActive:
                        appController && appController.currentPage === modelData.page

                    Rectangle {
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                        radius: 12
                        color: parent.isActive ? "#2E2A27" : (navItemMa.containsMouse ? "#252220" : "transparent")
                        Behavior on color { ColorAnimation { duration: 100 } }
                    }

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 4

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: modelData.icon
                            font.pixelSize: 22
                            color: parent.parent.isActive ? "#FFFFFF" : "#6B635C"
                        }

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: modelData.label
                            font.pixelSize: 10
                            font.weight: Font.Medium
                            color: parent.parent.isActive ? "#C4956A" : "#4E4842"
                        }
                    }

                    MouseArea {
                        id: navItemMa
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
                                case "settings": appController.showSettings(); break
                            }
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // Mirror status dot
            ColumnLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: 4
                spacing: 4

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 8; height: 8; radius: 999
                    color: mirrorDisplay && mirrorDisplay.mode !== "idle" ? "#C4956A" : "#3A3430"
                    ToolTip.visible: _dotMa.containsMouse
                    ToolTip.text: "Mirror: " + (mirrorDisplay ? mirrorDisplay.mode : "—")
                    MouseArea { id: _dotMa; anchors.fill: parent; hoverEnabled: true }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Mirror"
                    font.pixelSize: 9
                    color: "#3A3430"
                }
            }
        }
    }

    // ── Status bar ────────────────────────────────────────────────────
    StatusBar {
        id: statusBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        statusText: appController ? appController.statusMessage : ""
        errorText:  appController ? appController.errorMessage  : ""
    }

    // ── Page content area ─────────────────────────────────────────────
    Item {
        id: content
        anchors {
            top: parent.top
            left: navStrip.right
            right: parent.right
            bottom: statusBar.top
        }

        Rectangle {
            anchors.fill: parent
            color: "#F7F5F2"
        }

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
                    console.error("PageLoader failed:", source)
            }
        }
    }
}
