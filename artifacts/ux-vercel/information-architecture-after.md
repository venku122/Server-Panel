# Information architecture after

## Panel scope

Primary: Servers, Activity, Jobs, Deployment, Settings.

Settings children: Ports, Cluster, Panel Users, Discord, About.

## Selected-server scope

Primary: Overview, Operations, Players, Workshop, Activity, Jobs, Settings.

Tools: Recordings. Sibling views: Players/Moderation, Recorder/Gallery, General/Gameplay/History.

## Workflow ownership

- Overview summarizes runtime, mission, players, node, software, ports, recent Activity, recent Jobs, and quick links.
- Operations owns lifecycle, mission rotation, commands, and less-common operations.
- Settings owns password, startup, gameplay, configuration, deletion, and history.
- Workshop owns library inspection and rotation review.
- Players owns roster actions; Moderation is its sibling.
- Recordings owns recorder setup and gallery browsing.

## Progressive disclosure

- Resource rows show identity/status and no more than the most useful controls.
- Menus hold secondary row actions.
- Sheets hold Activity, Job, Workshop, and configuration-version detail.
- Mobile renders the same detail as bottom drawers.
- Modals remain the blocking boundary for restore, Workshop mutation review, and destructive decisions.
