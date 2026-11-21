# SE431 Demo Guide

Open SE431_Demo.mp4. The video captures the live console running Python and Git. It includes on-screen explanations and a locally generated English voice-over. The screen shows the review at commit 07, before commit 08 recorded the delivery files.

| Chapter | What to show and explain |
|---|---|
| 1. Legacy program | Open the supplied text and the separate executable copy. Show the indentation and entry-guard repair. Run the original one-copy flow on a temporary SQLite database. |
| 2. MR-01 | Search for Clean Code at 2/2. Borrow twice, see the third request rejected, return loan 1 and search again to show 1/2. |
| 3. MR-02 | Repeat the same book actions with the DuckDB engine. Run the importer on the temporary legacy fixture. Check the counts and the unchanged source file. |
| 4. Refactoring | Compare the actual stage 03 and stage 04 code. Explain the named member and item checks, the separate command-line adapter, named records and the fine helper. |
| 5. Reuse | Search for and borrow the demo projector. Explain the shared lending service and the separate sample equipment policy. |
| 6. Review fixes | Search for école and École on both engines. Show that the returned loan flag matches the stored flag and a duplicate return leaves stock unchanged. |
| 7. Tests and metrics | Run the full suite and show the actual summary. Compare the legacy script, maintenance prototype and refactored package. Explain why added features increased LOC. |
| 8. Git | Open the actual log and diff. Point out the six original stages and commit 07. The local bundle also records commit 08 with the review files and this video. |

## Questions to practice

- Why does the lowercase accented search not match the capital accented letter? The original SQLite search folds English ASCII letters only. The replacement engine follows the same rule.
- Why is a loan ID needed for returns? It identifies the open loan when the same member has two copies.
- Why does the test wait 25 hours past the due date? The legacy fine counts completed late days, so the expected fine is one unit.
- What was migrated? A generated fixture with two members, three items and one loan. Database records for the university were not supplied.
- Where is SQL now? In the storage and migration code. LendingService calls the Storage interface.

The four output logs and walkthrough_evidence.json capture real runs. From a clone of the bundle with development requirements installed, Demo/screen_demo.py runs the live walkthrough in the terminal. The application can also be run from the extracted ZIP using the README.
