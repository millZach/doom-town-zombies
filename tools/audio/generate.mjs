/**
 * generate.mjs — ElevenLabs generation driver.
 *
 *   node tools/audio/generate.mjs <phase>
 *
 * Phases: stingers | zombies | hounds | human | special | vox | all
 *
 * Every call is logged to tools/audio/elevenlabs_log.csv. Files that already
 * exist are skipped, so re-running is free. The budget guard stops the run
 * before it can cross BUDGET.
 */
import { balance, sfx, tts, spentFromLog, sleep, primeUsage } from './el_lib.mjs';

/** Hard ceiling on *total account usage* (used + this run). */
const BUDGET = 9700;

/* Deep, rough male voice for the announcer — processed into a PA later. */
const ANNOUNCER_VOICE = 'SOYHLrjzK2X1ezoPC6cr'; // Harry — Fierce Warrior

const NO_MUSIC = 'No music, no melody, no instruments playing a tune.';

const JOBS = {
  /* ---------------------------------------------------------- stingers --- */
  stingers: [
    {
      name: 'round_end_a', file: 'stinger/round_end_a.mp3', seconds: 7, influence: 0.55,
      prompt: 'Dark ominous cinematic horror sting. A deep male choir swells slowly out of silence, '
        + 'a distant low church bell tolls once, a subterranean drone underneath, then everything '
        + 'dissolves into a long cavernous reverberant tail. Mournful and heavy. '
        + 'Only low and low-mid frequencies, muffled and distant, nothing bright, '
        + 'no screech, no shriek, no high metallic ringing, no percussion.',
    },
    {
      name: 'round_end_b', file: 'stinger/round_end_b.mp3', seconds: 7, influence: 0.5,
      prompt: 'Eerie abandoned-church sting: a huge bronze bell tolls once far away in fog, '
        + 'low male voices hum a slow minor chord beneath it, a reversed swell rises and collapses '
        + 'into deep reverb. Dark, sombre, warm, heavily muffled, bass-heavy, '
        + 'no bright highs, no screeching, no sharp attacks.',
    },
    {
      name: 'round_end_c', file: 'stinger/round_end_c.mp3', seconds: 7, influence: 0.45,
      prompt: 'Low mournful orchestral swell in an enormous stone cathedral: bowed double basses '
        + 'and a pipe organ pedal note grow together, a single deep bell strike, a slow decay into '
        + 'a long dark reverb tail. Solemn, ominous, dusty. Warm and dark, no treble, no shrillness.',
    },
    {
      name: 'round_start_a', file: 'stinger/round_start_a.mp3', seconds: 6, influence: 0.5,
      prompt: 'Ominous low drone sting announcing something terrible arriving. Subterranean choir '
        + 'hum rising from nothing, one deep bell struck far away, dust and cold wind, '
        + 'collapsing into cavernous reverb. Very dark, muffled, felt more than heard. '
        + 'No bright tones, no screech, no shriek, no high ringing.',
    },
    {
      name: 'round_start_b', file: 'stinger/round_start_b.mp3', seconds: 6, influence: 0.45,
      prompt: 'Slow dread-filled rise: a deep sub bass swell, distant low male voices moaning in '
        + 'unison, a muffled bell toll, a cold gust, ending in a long dark reverberation. '
        + 'Heavy, sombre, low frequency, dull and distant, nothing sharp or piercing.',
    },
    {
      name: 'hellround_start_a', file: 'stinger/hellround_start_a.mp3', seconds: 6, influence: 0.5,
      prompt: 'Distant thunder rolling across a dead sky, a huge demonic wolf growling underneath, '
        + 'a dissonant low string cluster swelling, ending in a cavernous rumbling tail. '
        + 'Menacing, subterranean, dark. Low frequencies only, no bright crack, no shriek.',
    },
    {
      name: 'hellround_start_b', file: 'stinger/hellround_start_b.mp3', seconds: 6, influence: 0.45,
      prompt: 'Hell opening: deep rolling thunder, a monstrous hound snarl buried in the low end, '
        + 'a dissonant detuned drone rising, embers and wind, long dark rumble tail. '
        + 'Heavy, muffled, ominous. No high frequencies, no screeching metal.',
    },
    {
      name: 'game_over_a', file: 'stinger/game_over_a.mp3', seconds: 11, influence: 0.5,
      prompt: 'Mournful funeral sting. A slow deep church organ chord fades in, one tolling bell, '
        + 'distant humming voices, everything dying away into an enormous hollow reverberation. '
        + 'Hopeless, resigned, very dark and soft. Warm low frequencies, no harsh highs, '
        + 'no screech, no sudden impact.',
    },
  ],

  /* ----------------------------------------------------------- zombies --- */
  zombies: [
    {
      name: 'zombie_groan_a', file: 'zombie/groan_a.mp3', seconds: 10, influence: 0.45,
      prompt: 'Four separate zombie groans, one after another with a second of silence between '
        + 'each. A single rotting undead man: wet guttural moan, low throaty groan, rasping '
        + 'breath dragged through a ruined throat. Deep, male, phlegmy, close microphone, dry. '
        + `${NO_MUSIC} No footsteps, no other sounds.`,
    },
    {
      name: 'zombie_groan_b', file: 'zombie/groan_b.mp3', seconds: 10, influence: 0.45,
      prompt: 'Four separate slow undead moans with silence between them. A shambling corpse '
        + 'exhaling: a long low mournful groan, a wet gurgling rattle, a sighing growl. '
        + 'Male, deep, hoarse, wet, close and dry recording. '
        + `${NO_MUSIC} No music, no reverb, no other creatures.`,
    },
    {
      name: 'zombie_groan_c', file: 'zombie/groan_c.mp3', seconds: 10, influence: 0.4,
      prompt: 'Four separate zombie vocalisations with pauses between: a rising hungry groan, '
        + 'a throaty grunt, a low breathy moan, a rasping growl. Rotting human male, '
        + 'guttural, dry, close-miked, unsettling but low pitched. '
        + `${NO_MUSIC} No screaming, no high pitched shrieking.`,
    },
    {
      name: 'zombie_crawler', file: 'zombie/crawler.mp3', seconds: 9, influence: 0.45,
      prompt: 'Three separate vocalisations from a legless crawling zombie, with pauses between: '
        + 'wet strained gurgling, a desperate choked hiss, a low drag-and-moan. '
        + 'Close, wet, phlegmy, pathetic and horrible. Low pitched, no shrieking. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'zombie_scream_a', file: 'zombie/scream_a.mp3', seconds: 8, influence: 0.5,
      prompt: 'Three separate sprinting-zombie attack screams with silence between them. '
        + 'A rabid undead man charging: a ragged roaring scream torn out of a wrecked throat, '
        + 'furious and animal. Male, raw, mid pitched, throaty rather than shrill. '
        + `${NO_MUSIC} Not a high pitched shriek.`,
    },
    {
      name: 'zombie_scream_b', file: 'zombie/scream_b.mp3', seconds: 8, influence: 0.45,
      prompt: 'Three separate enraged undead roars with pauses between them: a furious rasping '
        + 'bellow, a shredded war-cry, a guttural charging roar. Deep male chest voice, '
        + 'aggressive and raw, distorted by a ruined throat. '
        + `${NO_MUSIC} No shrill screaming, no whistling.`,
    },
    {
      name: 'zombie_attack_a', file: 'zombie/attack_a.mp3', seconds: 7, influence: 0.5,
      prompt: 'Four short zombie attack snarls with brief pauses between them. A corpse lunging '
        + 'and biting: sharp wet snarl, snapping jaws, a strained grunt of effort. '
        + 'Close, aggressive, guttural, male. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'zombie_attack_b', file: 'zombie/attack_b.mp3', seconds: 7, influence: 0.45,
      prompt: 'Four short undead lunge sounds with pauses: a wet bark, a throaty hiss-snarl, '
        + 'teeth snapping, a choked aggressive grunt. Very close microphone, dry, nasty, '
        + 'low to mid pitched. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'zombie_death_a', file: 'zombie/death_a.mp3', seconds: 9, influence: 0.5,
      prompt: 'Three separate zombie death sounds with silence between them. An undead body '
        + 'finally giving out: a long gurgling death rattle, air leaving a punctured chest, '
        + 'a wet collapsing moan trailing to nothing. Deep, male, wet, close and dry. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'zombie_death_b', file: 'zombie/death_b.mp3', seconds: 9, influence: 0.45,
      prompt: 'Three separate undead death vocalisations with pauses: a choked descending groan, '
        + 'a bubbling last breath, a hollow sighing rattle that fades out. '
        + 'Low pitched, wet, hoarse, male, close-miked. '
        + `${NO_MUSIC} No shrieking.`,
    },
    {
      name: 'zombie_pain', file: 'zombie/pain.mp3', seconds: 7, influence: 0.45,
      prompt: 'Four short zombie pain grunts with pauses between: a wet impact grunt, '
        + 'a rasping yelp, a choked snarl of pain, a hollow winded groan. '
        + 'Undead male, guttural, dry close recording, mid-low pitch. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'zombie_rise', file: 'zombie/rise.mp3', seconds: 9, influence: 0.45,
      prompt: 'Two separate sequences with a pause between: dry earth and gravel shifting and '
        + 'falling as something drags itself up out of the ground, wooden boards splintering, '
        + 'followed by a long wet undead groan. Dirt, grit, scraping, then a guttural moan. '
        + `${NO_MUSIC}`,
    },
  ],

  /* ------------------------------------------------------------ hounds --- */
  hounds: [
    {
      name: 'hound_growl', file: 'hound/growl.mp3', seconds: 8, influence: 0.5,
      prompt: 'Three separate low growls from an enormous hellhound, with pauses between them. '
        + 'A huge demonic dog: a rumbling chest growl, a menacing rolling snarl, a warning '
        + 'grumble. Very deep, gravelly, wet, close microphone, dry. '
        + `${NO_MUSIC} No barking, no yelping.`,
    },
    {
      name: 'hound_bite', file: 'hound/bite.mp3', seconds: 7, influence: 0.5,
      prompt: 'Four short hellhound attack sounds with pauses: an explosive snarling lunge, '
        + 'jaws snapping shut hard, a savage growling bark, a wet tearing snarl. '
        + 'Huge demonic dog, deep and aggressive, close and dry. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'hound_death', file: 'hound/death.mp3', seconds: 7, influence: 0.45,
      prompt: 'Three separate hellhound death sounds with pauses between: a pained yelp falling '
        + 'into a mournful howl, a wet collapsing whine, a final rattling breath. '
        + 'Enormous demonic dog, deep, hoarse, dying. '
        + `${NO_MUSIC}`,
    },
  ],

  /* ------------------------------------------------------------- human --- */
  human: [
    {
      name: 'player_hurt', file: 'human/hurt.mp3', seconds: 7, influence: 0.45,
      prompt: 'Four short male pain grunts with pauses between: a sharp winded "ugh", '
        + 'a gritted hiss of pain, a heavy impact grunt, a strained groan. '
        + 'A tough adult man taking hits, close microphone, dry, no words. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'player_down', file: 'human/down.mp3', seconds: 6, influence: 0.45,
      prompt: 'A man collapsing badly wounded: a long agonised groan sliding into ragged wet '
        + 'breathing and a despairing exhale. Adult male, close, dry, no words. '
        + `${NO_MUSIC}`,
    },
    {
      name: 'player_effort', file: 'human/effort.mp3', seconds: 7, influence: 0.4,
      prompt: 'Six short male exertion sounds with pauses between: jumping grunts, landing '
        + 'exhales, sharp breaths of effort. Adult man, athletic, close dry microphone, '
        + 'no words. '
        + `${NO_MUSIC}`,
    },
  ],

  /* ----------------------------------------------------------- special --- */
  special: [
    {
      name: 'box_teddy', file: 'special/box_teddy.mp3', seconds: 5, influence: 0.5,
      prompt: 'A creepy toy music-box teddy bear laughing: a distorted childlike giggle turning '
        + 'wrong and demonic, with a swirling whoosh as it is snatched away. '
        + 'Unsettling, slightly detuned, lo-fi. Not shrill.',
    },
    {
      name: 'power_on', file: 'special/power_on.mp3', seconds: 6, influence: 0.5,
      prompt: 'An enormous rusted electrical switch is thrown: a heavy metal clunk, a deep '
        + 'transformer hum spinning up, fluorescent tubes flickering and striking on, '
        + 'settling into a steady industrial hum. Weighty, mechanical, low frequency.',
    },
    {
      name: 'raygun_fire', file: 'special/raygun_fire.mp3', seconds: 5, influence: 0.55,
      prompt: 'Three separate shots from a retro science-fiction ray gun, with pauses between. '
        + 'A thick wobbling plasma "pew" with a descending pitch, a warm electrical zap and a '
        + 'short resonant tail. Chunky and analogue, not thin, not shrill.',
    },
    {
      name: 'raygun_impact', file: 'special/raygun_impact.mp3', seconds: 4, influence: 0.5,
      prompt: 'Two separate energy-weapon impacts with a pause between: a plasma bolt bursting '
        + 'against a wall, a wet electrical crackle and a low resonant boom, fizzing away. '
        + 'Warm, thick, low-mid heavy.',
    },
    {
      name: 'pap_upgrade', file: 'special/pap_upgrade.mp3', seconds: 7, influence: 0.5,
      prompt: 'A grimy homemade machine processing a weapon: servos whirring, a hydraulic press '
        + 'thumping, an electrical charge building and discharging, a hiss of steam, then a '
        + 'satisfying mechanical clunk as a tray slides out. Industrial, greasy, mechanical.',
    },
    {
      name: 'hellhound_spawn', file: 'special/hellhound_spawn.mp3', seconds: 5, influence: 0.5,
      prompt: 'A violent lightning strike hitting the ground close by: a crackling electrical '
        + 'discharge, an enormous thunderclap, and a long rolling rumble away into the distance. '
        + 'Huge, low, powerful.',
    },
    {
      name: 'nuke_blast', file: 'special/nuke_blast.mp3', seconds: 6, influence: 0.5,
      prompt: 'A massive distant nuclear detonation: a deep sub-bass whump, a rolling shockwave, '
        + 'debris and a long decaying rumble across an empty landscape. '
        + 'Enormous, low frequency, no crack, no high frequencies.',
    },
    {
      name: 'powerup_spawn', file: 'special/powerup_spawn.mp3', seconds: 4, influence: 0.5,
      prompt: 'Two separate magical pickup appearing sounds with a pause between: a shimmering '
        + 'electrical materialisation, a warm rising chime and a soft airy whoosh. '
        + 'Pleasant, glassy but soft, not piercing.',
    },
    {
      name: 'powerup_grab', file: 'special/powerup_grab.mp3', seconds: 3, influence: 0.5,
      prompt: 'Two separate collect sounds with a pause between: a bright warm swoosh with a '
        + 'short ascending chime and a soft energy absorb. Satisfying, rounded, not shrill.',
    },
    {
      name: 'explosion_big', file: 'special/explosion_big.mp3', seconds: 6, influence: 0.5,
      prompt: 'Two separate grenade explosions with a pause between: a sharp concussive blast, '
        + 'a punch of low-end, dirt and debris raining down, and a short slapback echo off '
        + 'nearby buildings. Outdoors, close, powerful, bassy.',
    },
    {
      name: 'box_music', file: 'special/box_music.mp3', seconds: 9, influence: 0.6,
      prompt: 'A creepy antique wind-up music box playing a slow, simple, detuned lullaby in a '
        + 'minor key, with the mechanism ticking underneath. Tinny, warped, slowing slightly, '
        + 'unsettling and nostalgic. Soft and distant, not bright or piercing.',
    },
  ],


  /* --------------------------------------------- second pass: more takes --- */
  more: [
    {
      name: 'zombie_groan_d', file: 'zombie/groan_d.mp3', seconds: 10, influence: 0.4,
      prompt: 'Four separate undead vocalisations with a second of silence between each: '
        + 'a long shuddering moan, a dry rattling exhale, a low hungry groan, a wet growl. '
        + 'One rotting man, deep chest voice, phlegmy, close dry microphone. '
        + 'No music, no footsteps, no screaming, nothing high pitched.',
    },
    {
      name: 'zombie_groan_e', file: 'zombie/groan_e.mp3', seconds: 10, influence: 0.45,
      prompt: 'Four separate zombie moans with pauses between them: a slow rising groan of '
        + 'hunger, a bubbling throat rattle, a weary drawn-out moan, a short guttural huff. '
        + 'Rotting male corpse, low, wet, close and dry. No music, no shrieking.',
    },
    {
      name: 'zombie_death_c', file: 'zombie/death_c.mp3', seconds: 9, influence: 0.45,
      prompt: 'Three separate undead final breaths with silence between: a long descending '
        + 'gurgle, a hollow wheeze emptying out, a wet choking rattle fading to nothing. '
        + 'Deep male, hoarse, close-miked, dry. No music.',
    },
    {
      name: 'zombie_scream_c', file: 'zombie/scream_c.mp3', seconds: 8, influence: 0.45,
      prompt: 'Three separate charging-zombie roars with pauses: a ragged chest bellow, '
        + 'a furious throat-shredding roar, a rasping battle cry. Male, raw, mid pitched, '
        + 'throaty and animal rather than shrill. No music, no high pitched shriek.',
    },
    {
      name: 'zombie_attack_c', file: 'zombie/attack_c.mp3', seconds: 7, influence: 0.45,
      prompt: 'Four short undead biting attacks with pauses between: jaws snapping, a wet '
        + 'tearing snarl, a lunging grunt, a savage hiss. Very close, dry, guttural, nasty. '
        + 'No music.',
    },
    {
      name: 'hound_growl_b', file: 'hound/growl_b.mp3', seconds: 8, influence: 0.45,
      prompt: 'Three separate deep growls from a gigantic demonic dog, with pauses between: '
        + 'a slow rolling chest rumble, a rising threatening snarl, a wet guttural grumble. '
        + 'Enormous, very deep, gravelly, close and dry. No barking, no music.',
    },
    {
      name: 'hound_bite_b', file: 'hound/bite_b.mp3', seconds: 7, influence: 0.45,
      prompt: 'Four short hellhound strikes with pauses: an explosive snarl as it lunges, '
        + 'teeth clashing shut, a ripping growl, a guttural snapping bark. Huge demonic dog, '
        + 'deep, savage, close and dry. No music.',
    },
    {
      name: 'hound_death_b', file: 'hound/death_b.mp3', seconds: 7, influence: 0.45,
      prompt: 'Three separate deaths of an enormous demonic dog, with pauses: a sharp yelp '
        + 'collapsing into a long mournful howl, a wet gurgling whine, a last shuddering '
        + 'breath. Deep, hoarse, dying. No music.',
    },
    {
      name: 'game_over_b', file: 'stinger/game_over_b.mp3', seconds: 11, influence: 0.45,
      prompt: 'A slow hopeless funeral sting: deep church organ chord decaying, a single '
        + 'far-off bell, low voices humming, dust and stillness, dissolving into an enormous '
        + 'hollow reverberation. Very dark, soft, warm, no harsh highs, no impact, no screech.',
    },
    {
      name: 'jingle_juggernog', file: 'jingle/juggernog.mp3', seconds: 6, influence: 0.6,
      prompt: 'A short cheerful 1950s American radio advertising jingle for a soft drink, '
        + 'played on a tinny old speaker: a few bars of upbeat brass and vibraphone with a '
        + 'plinky ending. Vintage, lo-fi, slightly warped. Warm and soft, not bright.',
    },
    {
      name: 'jingle_speedcola', file: 'jingle/speedcola.mp3', seconds: 6, influence: 0.6,
      prompt: 'A short bouncy 1950s soda-shop advertising jingle on a scratchy old radio: '
        + 'quick pizzicato strings and a xylophone flourish, ending on a bright little chord. '
        + 'Vintage, lo-fi, warm and rounded, nothing piercing.',
    },
    {
      name: 'jingle_quickrevive', file: 'jingle/quickrevive.mp3', seconds: 6, influence: 0.6,
      prompt: 'A short old-fashioned patent-medicine advertising jingle on a worn gramophone: '
        + 'a slow waltzing melody on a tack piano and muted horn, warm and slightly sinister, '
        + 'ending on a soft chime. Vintage, lo-fi, muffled, not bright.',
    },
    {
      name: 'jingle_doubletap', file: 'jingle/doubletap.mp3', seconds: 6, influence: 0.6,
      prompt: 'A short swinging 1940s big-band advertising jingle through a cheap tube radio: '
        + 'a snappy muted-trumpet riff with a walking bass and a rimshot to finish. '
        + 'Vintage, lo-fi, warm, no harsh treble.',
    },
  ],

  /* --------------------------------------------------------- announcer --- */
  vox: [
    { name: 'vox_max_ammo', file: 'vox/max_ammo.mp3', text: 'Max Ammo!' },
    { name: 'vox_insta_kill', file: 'vox/insta_kill.mp3', text: 'Insta-Kill!' },
    { name: 'vox_double_points', file: 'vox/double_points.mp3', text: 'Double Points!' },
    { name: 'vox_nuke', file: 'vox/nuke.mp3', text: 'Kaboom!' },
    { name: 'vox_carpenter', file: 'vox/carpenter.mp3', text: 'Carpenter!' },
    { name: 'vox_fire_sale', file: 'vox/fire_sale.mp3', text: 'Fire Sale!' },
  ],
};

async function main() {
  const phase = process.argv[2] || 'all';
  const phases = phase === 'all' ? Object.keys(JOBS) : [phase];
  const b0 = await primeUsage();
  console.log(`[balance] used ${b0.used} / ${b0.limit}  (budget ceiling ${BUDGET})`);
  let used = b0.used;

  for (const ph of phases) {
    const jobs = JOBS[ph];
    if (!jobs) { console.log(`unknown phase ${ph}`); continue; }
    for (const j of jobs) {
      // Guard estimate. The account is billed ~11 credits per requested second
      // (measured), not the documented 40, so the guard uses the measured rate
      // with headroom; `used` is re-read from the API between phases.
      const cost = ph === 'vox' ? j.text.length : Math.round(j.seconds * 14);
      if (used + cost > BUDGET) {
        console.log(`[stop] ${j.name} would take ${used + cost} past the ${BUDGET} budget`);
        return;
      }
      try {
        const spent = ph === 'vox'
          ? await tts({ ...j, voiceId: ANNOUNCER_VOICE })
          : await sfx(j);
        used += spent;
        console.log(`${spent ? '+' : '='} ${j.name.padEnd(20)} ${String(spent).padStart(4)} cr   total ${used}`);
        if (spent) await sleep(700);
      } catch (e) {
        console.log(`! ${j.name}: ${e.message}`);
      }
    }
  }
  const b1 = await balance();
  console.log(`[balance] used ${b1.used} / ${b1.limit}; log total ${spentFromLog()}`);
}

main();
