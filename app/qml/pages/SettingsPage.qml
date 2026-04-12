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
            width: root.width
            anchors { leftMargin: 24; rightMargin: 24 }

            // ── Header ────────────────────────────────────────────────
            PageHeader {
                Layout.fillWidth: true
                title: "Settings"
                subtitle: "Camera, display, and screen configuration."
                onBackClicked: appController.showDashboard()
            }

            // ── Section: Camera ───────────────────────────────────────
            SectionHeader { text: "Camera" }

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
                    implicitWidth: 200
                }
            }

            SettingRow {
                label: "Current backend"
                description: settingsController.cameraBackendLabel
            }

            SettingRow {
                label: "Resolution"
                description: settingsController.cameraWidth + "×" + settingsController.cameraHeight
                             + " @ " + settingsController.cameraFps + " fps"
            }

            // ── Section: Mirror display ───────────────────────────────
            SectionHeader { text: "Mirror Display" }

            SettingRow {
                label: "Orientation"
                description: settingsController.mirrorOrientationDegrees + "°"

                RowLayout {
                    spacing: 8
                    Repeater {
                        model: [0, 90, 180, 270]

                        AppButton {
                            text: modelData + "°"
                            variant: settingsController.mirrorOrientationDegrees === modelData
                                     ? "primary" : "secondary"
                            implicitWidth: 64
                            implicitHeight: 38
                            onClicked: settingsController.setMirrorOrientation(modelData)
                        }
                    }
                }
            }

            SettingRow {
                label: "Compare fill mode"
                description: "Crop to fill panes vs fit entire frame"

                Switch {
                    checked: settingsController.compareFillCrop
                    onCheckedChanged: settingsController.setCompareFillCrop(checked)
                }
            }

            RowLayout {
                Layout.leftMargin: 0
                spacing: 12

                AppButton {
                    text: "Test Mirror"
                    variant: "secondary"
                    onClicked: settingsController.showMirrorTest()
                }

                AppButton {
                    text: "Hide Test"
                    variant: "ghost"
                    onClicked: settingsController.hideMirrorTest()
                }
            }

            // ── Section: Screens ──────────────────────────────────────
            SectionHeader { text: "Screens" }

            SettingRow {
                label: "Control screen"
                description: "Which display shows the UI"

                SpinBox {
                    from: 0
                    to: Math.max(0, settingsController.availableScreens.length - 1)
                    value: settingsController.controlScreenIndex
                    onValueModified: settingsController.setControlScreenIndex(value)
                    implicitWidth: 90
                }
            }

            SettingRow {
                label: "Mirror screen"
                description: "Which display shows the mirror"

                SpinBox {
                    from: 0
                    to: Math.max(0, settingsController.availableScreens.length - 1)
                    value: settingsController.mirrorScreenIndex
                    onValueModified: settingsController.setMirrorScreenIndex(value)
                    implicitWidth: 90
                }
            }

            AppButton {
                text: "Apply Screen Assignment"
                onClicked: settingsController.applyScreenAssignment()
            }

            // Detected screens
            Repeater {
                model: settingsController.availableScreens

                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: 8
                    color: "#f0e8e2"
                    border.width: 1
                    border.color: "#d6cdc5"

                    Text {
                        anchors { fill: parent; leftMargin: 12 }
                        verticalAlignment: Text.AlignVCenter
                        text: modelData.label
                        font.pixelSize: 12
                        color: "#6b6661"
                    }
                }
            }

            // ── Section: Diagnostics ──────────────────────────────────
            SectionHeader { text: "Diagnostics" }

            Repeater {
                model: Object.entries(settingsController.dependenciesStatus || {})

                SettingRow {
                    label: modelData[0]
                    description: modelData[1] ? "Found" : "Not found"

                    Rectangle {
                        width: 12; height: 12; radius: 999
                        color: modelData[1] ? "#4c8c5a" : "#8c3a3a"
                    }
                }
            }

            // ── Session info ───────────────────────────────────────────
            SectionHeader { text: "Session" }

            SettingRow {
                label: "Active session ID"
                description: sessionController.activeSession
                             ? sessionController.activeSession.id.substring(0, 16) + "…"
                             : "None"
            }

            SettingRow {
                label: "Looks recorded"
                description: sessionController.videoCount.toString()
            }

            RowLayout {
                spacing: 12

                AppButton {
                    text: "New Session"
                    variant: "secondary"
                    onClicked: {
                        sessionController.newSession()
                        galleryController.refresh()
                    }
                }

                AppButton {
                    text: "End Session"
                    variant: "ghost"
                    onClicked: {
                        sessionController.endSession()
                        galleryController.refresh()
                    }
                }
            }

            Item { Layout.preferredHeight: 32 }
        }
    }

    // ── Local sub-components ──────────────────────────────────────────

    component SectionHeader: Text {
        Layout.fillWidth: true
        Layout.topMargin: 20
        Layout.bottomMargin: 4
        font.pixelSize: 11
        font.weight: Font.Bold
        color: "#a09590"
        letterSpacing: 1.2
    }

    component SettingRow: Item {
        property string label: ""
        property string description: ""

        Layout.fillWidth: true
        implicitHeight: 48

        ColumnLayout {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            spacing: 1

            Text {
                text: parent.parent.label
                font.pixelSize: 14
                color: "#3c3530"
            }

            Text {
                text: parent.parent.description
                font.pixelSize: 11
                color: "#9d9590"
                visible: text.length > 0
            }
        }
    }
}
