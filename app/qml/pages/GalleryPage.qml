// My Looks — gallery of recorded videos with compare/export actions.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 14

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: "My Looks"
            subtitle: galleryController.videoCount + " look"
                      + (galleryController.videoCount === 1 ? "" : "s")
                      + (galleryController.selectedCount > 0
                         ? "  ·  " + galleryController.selectedCount + " selected"
                         : "")
            onBackClicked: appController.showDashboard()
        }

        // ── Selection action bar ──────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            visible: galleryController.selectedCount > 0
            height: 60
            radius: 14
            color: "#1C1917"

            RowLayout {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                spacing: 10

                AppButton {
                    text: "Play"
                    variant: "ghost"
                    enabled: galleryController.canPlay
                    implicitHeight: 40
                    contentItem: Text {
                        text: parent.text; font.pixelSize: 14; font.weight: Font.DemiBold
                        color: parent.enabled ? "#FFFFFF" : "#6B635C"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: galleryController.playSelected()
                }

                AppButton {
                    text: "Compare"
                    variant: "ghost"
                    enabled: galleryController.canCompare
                    implicitHeight: 40
                    contentItem: Text {
                        text: parent.text; font.pixelSize: 14; font.weight: Font.DemiBold
                        color: parent.enabled ? "#FFFFFF" : "#6B635C"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: galleryController.compareSelected()
                }

                AppButton {
                    text: "Live Compare"
                    variant: "ghost"
                    enabled: galleryController.canLiveCompare
                    implicitHeight: 40
                    contentItem: Text {
                        text: parent.text; font.pixelSize: 14; font.weight: Font.DemiBold
                        color: parent.enabled ? "#FFFFFF" : "#6B635C"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: galleryController.liveCompareSelected()
                }

                AppButton {
                    text: "Share"
                    variant: "ghost"
                    enabled: galleryController.canPlay
                    implicitHeight: 40
                    contentItem: Text {
                        text: parent.text; font.pixelSize: 14; font.weight: Font.DemiBold
                        color: parent.enabled ? "#C4956A" : "#6B635C"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: exportController.exportVideo(galleryController.selectedIds[0])
                }

                AppButton {
                    text: "Delete"
                    variant: "ghost"
                    enabled: galleryController.canPlay
                    implicitHeight: 40
                    contentItem: Text {
                        text: parent.text; font.pixelSize: 14; font.weight: Font.DemiBold
                        color: parent.enabled ? "#FF8080" : "#6B635C"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: deleteConfirm.open()
                }

                Item { Layout.fillWidth: true }

                // Clear selection
                Rectangle {
                    width: 32; height: 32; radius: 999
                    color: "#2E2A27"

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 13
                        color: "#9A9088"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: galleryController.clearSelection()
                    }
                }
            }
        }

        // ── Selection hint text ───────────────────────────────────────
        Text {
            visible: galleryController.videoCount > 0 && galleryController.selectedCount === 0
            text: "Tap a card to play  ·  Tap ○ to select for compare"
            font.pixelSize: 12
            color: "#A09890"
        }

        Text {
            visible: galleryController.selectedCount === 1
            text: "Select one more look to compare side-by-side"
            font.pixelSize: 12
            color: "#C4956A"
        }

        Text {
            visible: galleryController.selectedCount === 2
            text: "Ready to compare — tap Compare above"
            font.pixelSize: 12
            color: "#C4956A"
        }

        // ── Video grid ───────────────────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: _flow.implicitWidth
            clip: true

            Flow {
                id: _flow
                width: root.width - 48
                spacing: 14

                Repeater {
                    model: galleryController.videos

                    VideoCard {
                        videoId:      modelData.id
                        title:        modelData.title
                        durationLabel: modelData.durationLabel
                        thumbnailUrl: modelData.thumbnailUrl
                        createdLabel: modelData.createdLabel
                        selected:     galleryController.selectedIds.indexOf(modelData.id) >= 0
                        selectionIndex: galleryController.selectedIds.indexOf(modelData.id) + 1

                        onTapped:         galleryController.playVideo(modelData.id)
                        onCheckboxTapped: galleryController.toggleSelect(modelData.id)
                    }
                }
            }
        }

        // ── Empty state ───────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: galleryController.videoCount === 0
            spacing: 14

            Item { Layout.fillHeight: true }

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                width: 80; height: 80; radius: 999
                color: "#F0EBE5"

                Text {
                    anchors.centerIn: parent
                    text: "▦"
                    font.pixelSize: 36
                    color: "#C4BCBA"
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "No looks yet"
                font.pixelSize: 20
                font.weight: Font.DemiBold
                color: "#1C1917"
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Record your first look and it will appear here."
                font.pixelSize: 14
                color: "#6B6560"
            }

            Item { Layout.preferredHeight: 8 }

            AppButton {
                Layout.alignment: Qt.AlignHCenter
                text: "Record a Look"
                onClicked: appController.showRecording()
            }

            Item { Layout.fillHeight: true }
        }
    }

    // ── Delete confirmation ───────────────────────────────────────────
    Popup {
        id: deleteConfirm
        anchors.centerIn: parent
        modal: true; focus: true
        padding: 28

        background: Rectangle {
            color: "#FFFFFF"
            radius: 20
            border.width: 1
            border.color: "#E8E2DC"
        }

        contentItem: ColumnLayout {
            spacing: 16
            width: 320

            Text {
                text: "Delete this look?"
                font.pixelSize: 18
                font.weight: Font.Bold
                color: "#1C1917"
            }

            Text {
                text: "This cannot be undone."
                font.pixelSize: 14
                color: "#6B6560"
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                AppButton {
                    Layout.fillWidth: true
                    text: "Cancel"
                    variant: "secondary"
                    onClicked: deleteConfirm.close()
                }

                AppButton {
                    Layout.fillWidth: true
                    text: "Delete"
                    variant: "danger"
                    onClicked: {
                        deleteConfirm.close()
                        galleryController.deleteVideo(galleryController.selectedIds[0])
                    }
                }
            }
        }
    }
}
