// Gallery page — horizontal scroll of video cards with selection for compare.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 16

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: "Gallery"
            subtitle: galleryController.videoCount + " look"
                      + (galleryController.videoCount === 1 ? "" : "s")
                      + (galleryController.selectedCount > 0
                         ? "  ·  " + galleryController.selectedCount + " selected"
                         : "")
            onBackClicked: appController.showDashboard()
        }

        // ── Contextual action toolbar ────────────────────────────────
        // Visible only while videos are selected; shows relevant actions.
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            visible: galleryController.selectedCount > 0

            AppButton {
                text: "Play"
                enabled: galleryController.canPlay
                onClicked: galleryController.playSelected()
            }

            AppButton {
                text: "Compare"
                enabled: galleryController.canCompare
                onClicked: galleryController.compareSelected()
            }

            AppButton {
                text: "Live Compare"
                enabled: galleryController.canLiveCompare
                onClicked: galleryController.liveCompareSelected()
            }

            Item { Layout.fillWidth: true }

            AppButton {
                text: "Clear"
                variant: "secondary"
                onClicked: galleryController.clearSelection()
            }
        }

        // ── Selection hint ───────────────────────────────────────────
        Text {
            visible: galleryController.videoCount > 0 && galleryController.selectedCount === 0
            text: "Tap a card to play  ·  Tap ○ to select for compare"
            font.pixelSize: 12
            color: "#a09590"
        }

        // ── Selection action hint ────────────────────────────────────
        Text {
            visible: galleryController.selectedCount === 1
            text: "1 selected — tap ○ on a second card to Compare, or choose an action above"
            font.pixelSize: 12
            color: "#a09590"
        }

        Text {
            visible: galleryController.selectedCount === 2
            text: "2 selected — ready to Compare"
            font.pixelSize: 12
            color: "#a09590"
        }

        // ── Video grid ───────────────────────────────────────────────
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: galleryFlow.implicitWidth
            clip: true

            Flow {
                id: galleryFlow
                width: root.width - 48
                spacing: 14

                Repeater {
                    model: galleryController.videos

                    VideoCard {
                        videoId: modelData.id
                        title: modelData.title
                        durationLabel: modelData.durationLabel
                        thumbnailUrl: modelData.thumbnailUrl
                        createdLabel: modelData.createdLabel
                        selected: galleryController.selectedIds.indexOf(modelData.id) >= 0
                        selectionIndex: galleryController.selectedIds.indexOf(modelData.id) + 1

                        onTapped: galleryController.playVideo(modelData.id)
                        onCheckboxTapped: galleryController.toggleSelect(modelData.id)
                    }
                }
            }
        }

        // ── Empty state ──────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: galleryController.videoCount === 0
            spacing: 12

            Item { Layout.fillHeight: true }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "▦"
                font.pixelSize: 48
                color: "#c4b8ac"
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "No looks recorded yet"
                font.pixelSize: 18
                color: "#8c8681"
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Record your first look to see it here."
                font.pixelSize: 13
                color: "#a09590"
            }

            Item { Layout.fillHeight: true }

            AppButton {
                Layout.alignment: Qt.AlignHCenter
                text: "Record a Look"
                onClicked: appController.showRecording()
            }

            Item { Layout.preferredHeight: 16 }
        }

        // ── Delete hint ──────────────────────────────────────────────
        Text {
            visible: galleryController.videoCount > 0
            Layout.alignment: Qt.AlignHCenter
            text: "To delete a video, tap it to open the player."
            font.pixelSize: 11
            color: "#b0a8a2"
        }
    }
}
