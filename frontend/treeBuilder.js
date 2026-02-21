/**
 * Tree Builder - Dynamically constructs the decision tree from API data
 */

/**
 * Build complete tree structure from API programs
 * @param {Array} programs - Programs from API
 * @param {Array} careerNodes - Original career progression nodes
 * @returns {Object} Complete NODES object
 */
export function buildTree(programs, careerNodes = []) {
  const nodes = {};

  // Root node
  nodes.root = {
    id: "root",
    phase: -1,
    label: "YOU TODAY\\nYear 0",
    salary: "220K PKR/mo\\nL3 Embedded AI",
    prob: 1.0,
    color: "#00ff9f",
    children: ["masters_root", "p1_promoted", "p1_notpromoted_stay", "p1_switch_local"]
  };

  // Build masters branch
  const mastersNodes = buildMastersBranch(programs);
  Object.assign(nodes, mastersNodes);

  // Add original career nodes (hardcoded for now, can be from API later)
  const careerNodesObj = buildCareerNodes();
  Object.assign(nodes, careerNodesObj);

  return nodes;
}

/**
 * Build masters branch dynamically from programs
 */
function buildMastersBranch(programs) {
  const nodes = {};

  // Masters root
  nodes.masters_root = {
    id: "masters_root",
    phase: 0,
    label: "🎓 Pursue\\nMasters Degree",
    salary: `${programs.length} programs\\n38 countries`,
    prob: 0.15,
    color: "#a29bfe",
    note: "Higher education path. Data loaded from database.",
    branchType: "masters",
    depth: 0,
    children: ["tier1_free_europe", "tier2_elite_us", "tier3_midtier_global", "tier4_asia_regional"]
  };

  // Group programs by funding tier
  const tierGroups = groupBy(programs, 'funding_tier');

  // Tier metadata
  const tierMeta = {
    tier1_free_europe: {
      label: "🎓 Free/Low\\nEurope",
      prob: 0.25,
      color: "#a29bfe",
      note: "Germany, Switzerland, Nordics. High ROI, easier admission (40-70%).",
      phase: 0,
      branchType: "masters",
      depth: 1
    },
    tier2_elite_us: {
      label: "🏆 Elite US\\nTop Tier",
      prob: 0.35,
      color: "#00e5ff",
      note: "MIT, Stanford, CMU, Berkeley. Hardest admission (5-15%).",
      phase: 0,
      branchType: "masters",
      depth: 1
    },
    tier3_midtier_global: {
      label: "🌍 Mid-Tier\\nGlobal",
      prob: 0.30,
      color: "#fd79a8",
      note: "Canada, UK, Australia. Balanced ROI, moderate admission (30-50%).",
      phase: 0,
      branchType: "masters",
      depth: 1
    },
    tier4_asia_regional: {
      label: "🏠 Asia &\\nRegional",
      prob: 0.10,
      color: "#00cec9",
      note: "India, Singapore, HK. Lower cost, Pakistan proximity.",
      phase: 0,
      branchType: "masters",
      depth: 1
    }
  };

  // Build tier nodes
  for (const [tierId, meta] of Object.entries(tierMeta)) {
    const tierPrograms = tierGroups[tierId] || [];
    const fieldGroups = groupBy(tierPrograms, 'field');
    const fieldIds = Object.keys(fieldGroups).map(field => `${tierId}_field_${makeId(field)}`);

    nodes[tierId] = {
      id: tierId,
      phase: meta.phase,
      label: meta.label,
      salary: `${tierPrograms.length} programs`,
      prob: meta.prob,
      color: meta.color,
      note: meta.note,
      branchType: meta.branchType,
      depth: meta.depth,
      children: fieldIds
    };

    // Build field nodes
    for (const [field, fieldPrograms] of Object.entries(fieldGroups)) {
      const fieldId = `${tierId}_field_${makeId(field)}`;
      const programIds = fieldPrograms.map(p => `prog_${p.id}`);

      nodes[fieldId] = {
        id: fieldId,
        phase: 0,
        label: `${getFieldEmoji(field)} ${field}\\n${fieldPrograms.length} programs`,
        salary: "Various unis",
        prob: 1.0 / Object.keys(fieldGroups).length,
        color: getFieldColor(field),
        note: `${fieldPrograms.length} ${field} programs in this tier.`,
        branchType: "masters",
        depth: 2,
        children: programIds
      };

      // Build program nodes
      for (const program of fieldPrograms) {
        const progId = `prog_${program.id}`;
        nodes[progId] = {
          id: progId,
          phase: 0,
          label: `${truncate(program.university_name, 20)}\\n${truncate(program.program_name, 25)}`,
          salary: formatSalary(program),
          prob: getAcceptanceProb(program.funding_tier),
          color: tierMeta[program.funding_tier].color,
          note: buildProgramNote(program),
          branchType: "masters",
          depth: 3,
          children: [], // Terminal for now
          // Store full program data for details panel
          _programData: program
        };
      }
    }
  }

  return nodes;
}

/**
 * Build career progression nodes (hardcoded for now)
 * TODO: Load from database
 */
function buildCareerNodes() {
  // This would normally come from the database
  // For now, return a simplified version of the original nodes
  return {
    p1_promoted: {
      id: "p1_promoted",
      phase: 0,
      label: "✦ Promoted to L4\\nat Motive",
      salary: "400–475K PKR/mo\\n+RSU uplift",
      prob: 0.52,
      color: "#00e5ff",
      note: "~50–55% chance if strong performer. RSU allocation jumps ~3x.",
      branchType: "corporate",
      depth: 0,
      children: []
    },
    p1_notpromoted_stay: {
      id: "p1_notpromoted_stay",
      phase: 0,
      label: "✗ Not Promoted\\nStay at Motive",
      salary: "255–270K PKR/mo\\n(increments only)",
      prob: 0.28,
      color: "#ff9f43",
      note: "Annual 10–15% increments. Risk of getting stuck.",
      branchType: "corporate",
      depth: 0,
      children: []
    },
    p1_switch_local: {
      id: "p1_switch_local",
      phase: 0,
      label: "↗ Leave Motive\\nJoin Local",
      salary: "320–420K PKR/mo",
      prob: 0.20,
      color: "#a29bfe",
      note: "30–50% salary jump. Lose Motive RSU vesting.",
      branchType: "corporate",
      depth: 0,
      children: []
    }
  };
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function groupBy(array, key) {
  return array.reduce((result, item) => {
    const group = item[key];
    if (!result[group]) result[group] = [];
    result[group].push(item);
    return result;
  }, {});
}

function makeId(str) {
  return str.toLowerCase().replace(/[^a-z0-9]/g, '_');
}

function truncate(str, maxLen) {
  if (!str) return '';
  return str.length > maxLen ? str.substring(0, maxLen - 3) + '...' : str;
}

function formatSalary(program) {
  let parts = [];
  if (program.y1_salary_usd) parts.push(`Y1: $${program.y1_salary_usd}K`);
  if (program.y10_salary_usd) parts.push(`Y10: $${program.y10_salary_usd}K`);
  return parts.join('\\n') || 'Salary data N/A';
}

function buildProgramNote(program) {
  let note = `${program.university_name}, ${program.country}. `;
  if (program.tuition_usd) note += `Tuition: $${program.tuition_usd}K. `;
  if (program.net_10yr_usd) note += `Net 10yr: $${program.net_10yr_usd}K. `;
  if (program.notes) note += program.notes;
  return note;
}

function getAcceptanceProb(tier) {
  const probs = {
    tier1_free_europe: 0.55,
    tier2_elite_us: 0.10,
    tier3_midtier_global: 0.40,
    tier4_asia_regional: 0.45
  };
  return probs[tier] || 0.50;
}

function getFieldEmoji(field) {
  const emojis = {
    'AI/ML': '🤖',
    'CS/SWE': '💻',
    'DS': '📊',
    'Quant/FE': '💰',
    'Actuarial': '📈',
    'DS/Analytics': '📊',
    'DS/Quant': '📊💰',
    'Math/Quant': '🔢',
    'Quant/DS': '💰📊'
  };
  return emojis[field] || '🎓';
}

function getFieldColor(field) {
  const colors = {
    'AI/ML': '#00ff9f',
    'CS/SWE': '#00e5ff',
    'DS': '#a29bfe',
    'Quant/FE': '#fdcb6e',
    'Actuarial': '#fd79a8',
    'DS/Analytics': '#74b9ff',
    'DS/Quant': '#81ecec',
    'Math/Quant': '#fab1a0',
    'Quant/DS': '#55efc4'
  };
  return colors[field] || '#636e72';
}
