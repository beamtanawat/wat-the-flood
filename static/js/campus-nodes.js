(function (root, factory) {
  "use strict";

  const nodes = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = { CAMPUS_NODES: nodes };
  } else {
    root.CAMPUS_NODES = nodes;
  }
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const poiPaper = "https://lexitron.nectec.or.th/public/NCIT_2010_Bangkok%20_Thailand/index_files/papers/81-p088.pdf";
  const mappedLocationNote = "Approximate mapped POI; not a confirmed sensor-installation position.";

  return [
    {
      id: "esp32-01",
      name: "E12 Engineering Building",
      shortName: "E12",
      latitude: 13.72764,
      longitude: 100.77245,
      mode: "LIVE",
      source: "backend",
      locationNote: mappedLocationNote,
      locationSource: `${poiPaper} (E12 Tower POI); https://oia.kmitl.ac.th/wp-content/uploads/2024/02/OIA-KMITL-fold-brochure.pdf (E12 Building, item 16)`,
    },
    {
      id: "sim-me-tower",
      name: "ME Tower",
      shortName: "ME Tower",
      latitude: 13.72766,
      longitude: 100.77348,
      mode: "SIM",
      source: "simulation",
      locationNote: mappedLocationNote,
      locationSource: `${poiPaper} (ME Tower / ME office POI)`,
      fixture: {
        device_status: "SIM",
        water_level_cm: 5.2,
        conductivity_ms_cm: 0.48,
        north_rms_v: 0.05,
        east_rms_v: 0.05,
        south_rms_v: 0.05,
        west_rms_v: 0.05,
        direction: null,
        direction_reason: "LOW_SIGNAL",
        gradient_v: 0,
        rule_risk: "NORMAL",
        ai_risk: "NORMAL",
        ai_confidence: 0.74,
      },
    },
    {
      id: "sim-sport-complex",
      name: "Sport Complex",
      shortName: "Sport",
      latitude: 13.73003,
      longitude: 100.77245,
      mode: "SIM",
      source: "simulation",
      locationNote: mappedLocationNote,
      locationSource: `${poiPaper} (Stadium / Sport complex POI); https://oia.kmitl.ac.th/wp-content/uploads/2024/02/OIA-KMITL-fold-brochure.pdf (Sport Complex, item 14)`,
      fixture: {
        device_status: "SIM",
        water_level_cm: 12.4,
        conductivity_ms_cm: 0.62,
        north_rms_v: 0.08,
        east_rms_v: 0.12,
        south_rms_v: 0.07,
        west_rms_v: 0.08,
        direction: "EAST",
        direction_reason: "DOMINANT_AXIS",
        gradient_v: 0.04,
        rule_risk: "MONITOR",
        ai_risk: "NORMAL",
        ai_confidence: 0.68,
      },
    },
    {
      id: "sim-telecom-tower",
      name: "Telecom Tower",
      shortName: "Telecom",
      latitude: 13.72744,
      longitude: 100.7762,
      mode: "SIM",
      source: "simulation",
      locationNote: mappedLocationNote,
      locationSource: `${poiPaper} (Telecom Tower / Telecom Engineering Department POI)`,
      fixture: {
        device_status: "SIM",
        water_level_cm: 16.1,
        conductivity_ms_cm: 0.91,
        north_rms_v: 0.09,
        east_rms_v: 0.42,
        south_rms_v: 0.08,
        west_rms_v: 0.11,
        direction: "EAST",
        direction_reason: "DOMINANT_AXIS",
        gradient_v: 0.31,
        rule_risk: "HIGH",
        ai_risk: "MONITOR",
        ai_confidence: 0.71,
      },
    },
    {
      id: "sim-a-tower",
      name: "A Tower",
      shortName: "A Tower",
      latitude: 13.72693,
      longitude: 100.77648,
      mode: "SIM",
      source: "simulation",
      locationNote: mappedLocationNote,
      locationSource: `${poiPaper} (A Tower / KMITL office POI)`,
      fixture: {
        device_status: "SIM",
        water_level_cm: 22.8,
        conductivity_ms_cm: 1.14,
        north_rms_v: 0.11,
        east_rms_v: 0.76,
        south_rms_v: 0.09,
        west_rms_v: 0.13,
        direction: "EAST",
        direction_reason: "DOMINANT_AXIS",
        gradient_v: 0.63,
        rule_risk: "CRITICAL",
        ai_risk: "HIGH",
        ai_confidence: 0.66,
      },
    },
  ];
});
