# AI usage note

**Tools used:**
Claude without using the agent file. 

**What I delegated:**
- `build.sh` and all the executables in `bin/` are by AI.
- Graphing code revision. 
- I also used help with deciding on a way to normalize my scoring scheme in the `guess_key_length` function because I'm not very experienced with making score weighing functions. 

**What I verified myself, and how:**
- The build runs with the example commands in `samples/README.md`.
- I run multiple trials with different designs of the key guess decision function and picked the best one. 

**One thing I learned from — or caught wrong in — the AI's output:**
- AI is pretty good at making the build file but it's very useless at helping me with `guess_key_length` and I eventually did not listen to whatever it said. 