# SE431 Demo Guide

Open SE431_Demo.mp4. It shows the captured output of real terminal runs. The captions explain each step. The terminal commands can be repeated using the README.

| Chapter | What to explain |
|---|---|
| Phase 1: legacy program | Show the original Python and SQLite flow. The shared database access and one-copy flag make changes harder. The supplied text was preserved and its syntax was repaired in a separate runnable copy. |
| MR-01: multiple copies | Search for Clean Code. Start at 2/2, borrow twice, and try the third request. Return loan 1 and search again to see 1/2. |
| MR-02: database replacement | Change the engine to DuckDB and run the same book workflow. Then run the importer on a generated legacy database. The importer reports two members, three items and one loan. |
| Phase 3: refactoring | Compare the long borrow method with the member and item checks in LendingService. Explain how the console, policies and repository are separated. |
| Phase 4: reusable domain | Explain the shared member, item and loan records, then show the projector borrowed on DuckDB under a demonstration policy. |
| Phase 5: quality | Use the recorded results from both engines. Compare the post-maintenance prototype with the final code to isolate the refactoring effect. |
| Phase 6: Git | Show the six ordered stages and name one change made at each stage. |

The SQLite and DuckDB book sessions, equipment session and migration output are recorded in the four evidence text files. The detailed runs are in walkthrough_evidence.json. Demo inventory and the migrated database are test fixtures.

