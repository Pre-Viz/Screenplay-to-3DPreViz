// Data for the scripts
const scriptsData = {
    script1: {
        name: 'script1.txt',
        video: '../demo/results/script1/4_final/script1_final.mp4',
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
        name: 'script2.txt',
        video: '../demo/results/script2/4_final/script2_final.mp4',
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
        name: 'script3.txt',
        video: '../demo/results/script3/4_final/script3_final.mp4',
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

// DOM Elements
const scriptBtns = document.querySelectorAll('.script-btn');
const scriptContent = document.getElementById('script-content');
const scriptName = document.getElementById('current-script-name');
const videoPlayer = document.getElementById('demo-video');
const videoContainer = document.querySelector('.video-container');

// Change Demo Function
function changeDemo(scriptId) {
    const data = scriptsData[scriptId];
    if (!data) return;

    // Update active state on buttons
    scriptBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.script === scriptId);
    });

    // Update Code Panel
    scriptContent.style.opacity = 0;
    setTimeout(() => {
        scriptName.textContent = data.name;
        scriptContent.textContent = data.content;
        scriptContent.style.opacity = 1;
    }, 200);

    // Update Video Panel with loading state
    videoContainer.classList.add('loading');
    
    // Create new source element
    const source = videoPlayer.querySelector('source');
    source.src = data.video;
    
    // Reload and play video
    videoPlayer.load();
    videoPlayer.play().catch(e => console.log("Autoplay prevented by browser", e));
    
    // Remove loading state when video can play
    videoPlayer.addEventListener('canplay', function onCanPlay() {
        videoContainer.classList.remove('loading');
        videoPlayer.removeEventListener('canplay', onCanPlay);
    });
}

// Add event listeners to buttons
scriptBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const scriptId = btn.dataset.script;
        // Don't do anything if it's already active
        if (!btn.classList.contains('active')) {
            changeDemo(scriptId);
        }
    });
});

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;
        
        const targetElement = document.querySelector(targetId);
        if (targetElement) {
            targetElement.scrollIntoView({
                behavior: 'smooth'
            });
        }
    });
});

// Navbar scroll effect
window.addEventListener('scroll', () => {
    const nav = document.querySelector('.navbar');
    if (window.scrollY > 50) {
        nav.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.4)';
        nav.style.padding = '1rem 0';
    } else {
        nav.style.boxShadow = 'none';
        nav.style.padding = '1.5rem 0';
    }
});
