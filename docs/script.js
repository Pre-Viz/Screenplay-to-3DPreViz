const scriptsData = {
    script1: {
        video: 'assets/script1_final.mp4',
        content: `EXT. BEACH - DAY

DEREK (26) stands near the water, looking out. SOPHIE (25) walks up and stops beside him.

                         SOPHIE
                         You didn't say goodbye last time either.

                         DEREK
                         I know. I'm sorry.

                         SOPHIE
                         Are you actually leaving? For good?

                         DEREK
                         I got the position. It's overseas.

Sophie nods slowly. She looks out at the water.

                         SOPHIE
                         When?

                         DEREK
                         Tomorrow morning.

                         SOPHIE
                         (laughs softly)
                         Of course it's tomorrow.

Derek turns to face her.

                         DEREK
                         You could come, you know.

                         SOPHIE
                         Don't.

She waves him off and starts walking away down the beach.

                         DEREK
                         Sophie.

She doesn't turn around. He watches her go.`
    },
    script2: {
        video: 'assets/script2_final.mp4',
        content: `INT. KITCHEN - MORNING

MARA (30) stands at the sink, washing dishes. JAKE (33) walks in and leans against the doorframe.

                         JAKE
                         You're up early.

                         MARA
                         Couldn't sleep.

Jake walks closer. Mara keeps her back to him.

                         JAKE
                         We need to talk.

                         MARA
                         I know.

                         JAKE
                         Then why do I feel like I'm the only one
                         trying?

Mara turns off the tap. She turns around.

                         MARA
                         Because you think talking fixes everything.

                         JAKE
                         It's better than saying nothing.

                         MARA
                         (quietly)
                         Not always.

She walks past him toward the door. Jake stands there alone.`
    },
    script3: {
        video: 'assets/script3_final.mp4',
        content: `INT. LIVING ROOM - DAY

LENA (21) and GEORGE (24) sit on the couch, looking at the TV. 

                          LENA
                          So, we're not even going to talk about it?

                          GEORGE
                          (sighs)

                          LENA
                          What?

                          GEORGE
                          There's nothing to even talk about.

                          LENA
                          Okay.
                          (gets up)
                          You can go to hell.

She walks away. George gets up.

                          GEORGE
                          Lena! Come on.`
    }
};

const scriptBtns = document.querySelectorAll('.script-btn');
const scriptContent = document.getElementById('script-content');
const videoPlayer = document.getElementById('demo-video');

function changeDemo(scriptId) {
    const data = scriptsData[scriptId];
    if (!data) return;

    scriptBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.script === scriptId);
    });

    scriptContent.textContent = data.content;
    
    const source = videoPlayer.querySelector('source');
    source.src = data.video;
    videoPlayer.load();
    videoPlayer.play().catch(e => console.log("Autoplay prevented:", e));
}

scriptBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        if (!btn.classList.contains('active')) {
            changeDemo(btn.dataset.script);
        }
    });
});

// Initialize with first script
changeDemo('script1');
