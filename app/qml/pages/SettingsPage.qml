// Settings page — camera, mirror orientation, screen assignment, diagnostics.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../components"

Item {
    id: root

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: root.width - 48
            x: 24
            spacing: 0

            // ── Header ────────────────────────────────────────────────
            PageHeader {
                Layout.fillWidth: true
                title: "Settings"
                subtitle: "Camera, display, and screen configuration."
                onBackClicked: appController.showDashboard()
            }

            // ── Camera ───────────────────────────────────────────────
            SectionLabel { text: "Camera" }
            SettingsCard {
                SettingRow {
                    label: "Backend"
                    description: "Which camera source to use"
                    ComboBox {
                        model: ["Auto detect", "Raspberry Pi camera", "USB webcam"]
                        currentIndex: {
                            var b = settingsController.cameraBackend
                            return b === "raspberry_pi" ? 1 : b === "usb" ? 2 : 0
                        }
                        onActivated: {
                            var keys = ["auto", "raspberry_pi", "usb"]
                            settingsController.setCameraBackend(keys[currentIndex])
                        }
                        font.pixelSize: 13
                        implicitWidth: 190
                    }
                }
                RowDivider {}
                SettingRow {
                    label: "Active backend"
                    description: settingsController.cameraBackendLabel
                }
                RowDivider {}
                SettingRow {
                    label: "Resolution"
                    description: settingsController.cameraWidth + "×" + settingsController.cameraHeight
                    RowLayout {
                        spacing: 6
                        Repeater {
                            model: [
                                { label: "720p",  w: 1280, h: 720  },
                                { label: "1080p", w: 1920, h: 1080 },
                            ]
                            AppButton {
                                text: modelData.label
                                variant: settingsController.cameraWidth === modelData.w
                                         ? "primary" : "secondary"
                                implicitWidth: 68; implicitHeight: 34
                                onClicked: settingsController.setCameraResolution(
                                    modelData.w, modelData.h, settingsController.cameraFps)
                            }
                        }
                    }
                }
                RowDivider {}
                SettingRow {
                    label: "Frame rate"
                    description: settingsController.cameraFps + " fps"
                    RowLayout {
                        spacing: 6
                        Repeater {
                            model: [30, 60]
                            AppButton {
                                text: modelData + " fps"
                                variant: settingsController.cameraFps === modelData
                                         ? "primary" : "secondary"
                                implicitWidth: 74; implicitHeight: 34
                                onClicked: settingsController.setCameraResolution(
                                    settingsController.cameraWidth,
                                    settingsController.cameraHeight,
                                    modelData)
                            }
                        }
                    }
                }
                RowDivider {}
                SettingRow {
                    label: "Mirror flip"
                    description: "Horizontally flip the live preview and recorded video"
                    Switch {
                        checked: settingsController.cameraMirrorFlip
                        onToggled: settingsController.setCameraMirrorFlip(checked)
                    }
                }
            }

            // ── Mirror Display ────────────────────────────────────────
            SectionLabel { text: "Mirror Display" }
            SettingsCard {
                SettingRow {
                    label: "Orientation"
                    description: settingsController.mirrorOrientationDegrees + "°"
                    RowLayout {
                        spacing: 6
                        Repeater {
                            model: [0, 90, 180, 270]
                            AppButton {
                                text: modelData + "°"
                                variant: settingsController.mirrorOrientationDegrees === modelData
                                         ? "primary" : "secondary"
                                implicitWidth: 56; implicitHeight: 34
                                onClicked: settingsController.setMirrorOrientation(modelData)
                            }
                        }
                    }
                }
                RowDivider {}
                SettingRow {
                    label: "Compare fill mode"
                    description: "Crop to fill panes, or letterbox to show the full frame"
                    Switch {
                        checked: settingsController.compareFillCrop
                        onToggled: settingsController.setCompareFillCrop(checked)
                    }
                }
                RowDivider {}
                SettingRow {
                    label: "Test pattern"
                    description: "Show a test card on the mirror display"
                    RowLayout {
                        spacing: 6
                        AppButton {
                            text: "Show"
                            variant: "secondary"
                            implicitWidth: 72; implicitHeight: 34
                            onClicked: settingsController.showMirrorTest()
                        }
                        AppButton {
                            text: "Hide"
                            variant: "ghost"
                            implicitWidth: 72; implicitHeight: 34
                            onClicked: settingsController.hideMirrorTest()
                        }
                    }
                }
            }

            // ── Screens ───────────────────────────────────────────────
            SectionLabel { text: "Screens" }
            SettingsCard {
                SettingRow {
                    label: "Auto-detect"
                    description: "Smallest screen → control, largest → mirror"
                    Switch {
                        checked: settingsController.screenAutoDetect
                        onToggled: settingsController.setScreenAutoDetect(checked)
                    }
                }

                // Auto-detect result
                Rectangle {
                    visible: settingsController.screenAutoDetect
                             && settingsController.autoScreenAssignment.available === true
                    Layout.fillWidth: true
                    height: _assignCol.implicitHeight + 20
                    color: "#F0F7F0"
                    ColumnLayout {
                        id: _assignCol
                        anchors {
                            left: parent.left; right: parent.right
                            verticalCenter: parent.verticalCenter
                            leftMargin: 16; rightMargin: 16
                        }
                        spacing: 4
                        Text {
                            text: "Control  →  " + settingsController.autoScreenAssignment.controlName
                                  + "  (" + settingsController.autoScreenAssignment.controlRes + ")"
                            font.pixelSize: 12; color: "#2E6B3A"
                        }
                        Text {
                            text: "Mirror   →  " + settingsController.autoScreenAssignment.mirrorName
                                  + "  (" + settingsController.autoScreenAssignment.mirrorRes + ")"
                            font.pixelSize: 12; color: "#2E6B3A"
                        }
                    }
                }

                RowDivider { visible: !settingsController.screenAutoDetect }
                SettingRow {
                    visible: !settingsController.screenAutoDetect
                    label: "Control screen"
                    description: "Index of the UI display"
                    SpinBox {
                        from: 0
                        to: Math.max(0, settingsController.availableScreens.length - 1)
                        value: settingsController.controlScreenIndex
                        onValueModified: settingsController.setControlScreenIndex(value)
                        implicitWidth: 90
                    }
                }
                RowDivider { visible: !settingsController.screenAutoDetect }
                SettingRow {
                    visible: !settingsController.screenAutoDetect
                    label: "Mirror screen"
                    description: "Index of the mirror display"
                    SpinBox {
                        from: 0
                        to: Math.max(0, settingsController.availableScreens.length - 1)
                        value: settingsController.mirrorScreenIndex
                        onValueModified: settingsController.setMirrorScreenIndex(value)
                        implicitWidth: 90
                    }
                }
                RowDivider {}
                SettingRow {
                    label: "Apply assignment"
                    description: "Move windows to their assigned screens now"
                    AppButton {
                        text: "Apply"
                        implicitWidth: 80; implicitHeight: 34
                        onClicked: settingsController.applyScreenAssignment()
                    }
                }

                // Connected screens list
                Repeater {
                    model: settingsController.availableScreens
                    Rectangle {
                        Layout.fillWidth: true
                        height: 34
                        color: "#F7F5F2"
                        Rectangle {
                            anchors { top: parent.top; left: parent.left; right: parent.right }
                            height: 1; color: "#E8E2DC"
                        }
                        Text {
                            anchors { fill: parent; leftMargin: 16 }
                            verticalAlignment: Text.AlignVCenter
                            text: modelData.label
                            font.pixelSize: 12; color: "#6B6560"
                        }
                    }
                }
            }

            // ── Camera Status ─────────────────────────────────────────
            SectionLabel { text: "Camera Status" }
            SettingsCard {
                Repeater {
                    model: Object.entries(settingsController.cameraBackendsStatus || {})
                    SettingRow {
                        label: modelData[0]
                        description: modelData[1] ? "Available" : "Not detected"
                        Rectangle {
                            width: 10; height: 10; radius: 999
                            color: modelData[1] ? "#4caf6a" : "#af4c4c"
                        }
                    }
                }
            }

            // ── Dependencies ──────────────────────────────────────────
            SectionLabel { text: "Dependencies" }
            SettingsCard {
                Repeater {
                    model: Object.entries(settingsController.dependenciesStatus || {})
                    SettingRow {
                        label: modelData[0]
                        description: modelData[1] ? "Found" : "Missing"
                        Rectangle {
                            width: 10; height: 10; radius: 999
                            color: modelData[1] ? "#4caf6a" : "#af4c4c"
                        }
                    }
                }
            }

            // ── Session ───────────────────────────────────────────────
            SectionLabel { text: "Session" }
            SettingsCard {
                SettingRow {
                    label: "Active session"
                    description: sessionController.activeSessionShortId.length > 0
                                 ? sessionController.activeSessionShortId + "…" : "None"
                }
                RowDivider {}
                SettingRow {
                    label: "Looks recorded"
                    description: sessionController.videoCount.toString()
                }
                RowDivider {}
                SettingRow {
                    label: "Session controls"
                    description: "Start a fresh session or close the current one"
                    RowLayout {
                        spacing: 6
                        AppButton {
                            text: "New"
                            variant: "secondary"
                            implicitWidth: 72; implicitHeight: 34
                            onClicked: { sessionController.newSession(); galleryController.refresh() }
                        }
                        AppButton {
                            text: "End"
                            variant: "ghost"
                            implicitWidth: 72; implicitHeight: 34
                            onClicked: {
                                sessionController.endSession()
                                galleryController.refresh()
                                loginController.startLogin()
                            }
                        }
                    }
                }
            }

            // ── Application ───────────────────────────────────────────
            SectionLabel { text: "Application" }
            SettingsCard {
                SettingRow {
                    label: "Quit application"
                    description: "Close the app and all camera processes"
                    AppButton {
                        text: "Quit"
                        variant: "danger"
                        implicitWidth: 80; implicitHeight: 34
                        onClicked: Qt.quit()
                    }
                }
            }

            Item { Layout.preferredHeight: 32 }
        }
    }

    // ── Inline components ─────────────────────────────────────────────

    // Uppercase section label above each card group
    component SectionLabel: Text {
        Layout.fillWidth: true
        Layout.topMargin: 24
        Layout.bottomMargin: 6
        font.pixelSize: 11
        font.weight: Font.Bold
        font.letterSpacing: 1.4
        font.capitalization: Font.AllUppercase
        color: "#A09890"
    }

    // Rounded card that groups related setting rows
    component SettingsCard: Rectangle {
        Layout.fillWidth: true
        Layout.topMargin: 2
        radius: 12
        color: "#FFFFFF"
        border.width: 1
        border.color: "#E8E2DC"
        clip: true
        implicitHeight: _cardLayout.implicitHeight
        default property alias rows: _cardLayout.data

        ColumnLayout {
            id: _cardLayout
            width: parent.width
            spacing: 0
        }
    }

    // A single setting row: label+description on the left, control on the right
    component SettingRow: Item {
        id: _rowRoot
        property string label: ""
        property string description: ""
        default property alias content: _controlSlot.data

        Layout.fillWidth: true
        implicitHeight: _inner.implicitHeight + 26

        RowLayout {
            id: _inner
            anchors {
                left: parent.left; right: parent.right
                leftMargin: 16; rightMargin: 16
                verticalCenter: parent.verticalCenter
            }
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    text: _rowRoot.label
                    font.pixelSize: 14
                    color: "#1C1917"
                    Layout.fillWidth: true
                }
                Text {
                    visible: _rowRoot.description.length > 0
                    text: _rowRoot.description
                    font.pixelSize: 12
                    color: "#6B6560"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            // Control area — children declared on SettingRow instances land here
            Item {
                id: _controlSlot
                implicitWidth: childrenRect.width
                implicitHeight: childrenRect.height
            }
        }
    }

    // 1 px horizontal rule between rows inside a card
    component RowDivider: Rectangle {
        Layout.fillWidth: true
        height: 1
        color: "#E8E2DC"
    }
}
