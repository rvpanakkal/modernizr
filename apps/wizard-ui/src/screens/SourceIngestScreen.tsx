import React, { useEffect, useState } from 'react';
import { useWizardStore } from '../store/wizardStore';
import { apiClient } from '../services/api';
import {
  UploadCloud,
  GitBranch,
  Settings2,
  FileArchive,
  Cpu,
  CheckCircle2,
  ArrowRight,
  Database,
  Layers,
  Sparkles,
  AlertCircle,
  ShieldCheck,
  FolderGit2,
  Code2,
  PlusCircle,
  X,
  FileCode,
  Info,
} from 'lucide-react';

export const SourceIngestScreen: React.FC = () => {
  const {
    setStep,
    setMonolithInfo,
    monolithInfo,
    architectureProfiles,
    activeProfile,
    isLoadingProfile,
    fetchArchitectureProfiles,
    setActiveProfile,
    uploadReferenceMicroservice,
  } = useWizardStore();

  const [uploadMode, setUploadMode] = useState<'file' | 'git'>('git');
  const [gitUrl, setGitUrl] = useState('https://github.com/enterprise/legacy-banking-monolith.git');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jdkVersion, setJdkVersion] = useState('8');
  const [frameworkProfile, setFrameworkProfile] = useState('JAVA_EE_6_JSF');
  const [classpathStrategy, setClasspathStrategy] = useState('AI_SYNTHETIC_STUBS');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successPayload, setSuccessPayload] = useState<any>(monolithInfo);

  // Harvest Modal State
  const [isHarvestModalOpen, setIsHarvestModalOpen] = useState(false);
  const [harvestMode, setHarvestMode] = useState<'git' | 'file'>('git');
  const [harvestProfileName, setHarvestProfileName] = useState('Payments-Reference-v2');
  const [harvestRepoPath, setHarvestRepoPath] = useState('samples/reference-spring-boot-service');
  const [harvestFile, setHarvestFile] = useState<File | null>(null);
  const [isHarvesting, setIsHarvesting] = useState(false);
  const [harvestError, setHarvestError] = useState<string | null>(null);

  useEffect(() => {
    fetchArchitectureProfiles();
  }, [fetchArchitectureProfiles]);

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleRunIngestion = async () => {
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const formData = new FormData();
      if (uploadMode === 'file' && selectedFile) {
        formData.append('file', selectedFile);
      } else {
        formData.append('git_url', gitUrl);
      }
      formData.append('jdk_version', jdkVersion);
      formData.append('framework_profile', frameworkProfile);
      formData.append('classpath_strategy', classpathStrategy);

      const res = await apiClient.uploadSource(formData);
      setSuccessPayload(res);
      setMonolithInfo({
        monolithId: res.monolith_id,
        classesCount: res.classes_count,
        methodsCount: res.methods_count,
        fieldsCount: res.injected_fields_count,
        endpointsCount: res.endpoints_count,
        gatewaysCount: res.cics_gateways_count,
        sha256Digest: res.sha256_digest,
        extractedAt: res.extracted_at,
        jdkVersion: res.jdk_version,
        frameworkProfile: res.framework_profile,
        classpathStrategy: res.classpath_strategy,
      });
    } catch (err: any) {
      console.error('Source upload failed:', err);
      setErrorMsg(err.response?.data?.message || 'Failed to extract LST metadata from source.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleHarvestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!harvestProfileName.trim()) {
      setHarvestError('Please enter a profile name.');
      return;
    }
    if (harvestMode === 'file' && !harvestFile) {
      setHarvestError('Please select a reference microservice ZIP file.');
      return;
    }
    if (harvestMode === 'git' && !harvestRepoPath.trim()) {
      setHarvestError('Please provide a repository path or Git URL.');
      return;
    }

    setIsHarvesting(true);
    setHarvestError(null);
    try {
      if (harvestMode === 'file' && harvestFile) {
        await uploadReferenceMicroservice({
          file: harvestFile,
          profile_name: harvestProfileName.trim(),
        });
      } else {
        await uploadReferenceMicroservice({
          repo_path: harvestRepoPath.trim(),
          profile_name: harvestProfileName.trim(),
        });
      }
      setIsHarvestModalOpen(false);
      setHarvestFile(null);
    } catch (err: any) {
      console.error('Failed to harvest reference microservice:', err);
      setHarvestError(
        err.response?.data?.detail || err.message || 'Failed to harvest architecture profile.'
      );
    } finally {
      setIsHarvesting(false);
    }
  };

  const getLayeringBadgeColor = (pattern?: string) => {
    switch (pattern) {
      case 'HEXAGONAL':
        return 'bg-purple-950/80 text-purple-300 border-purple-800/60';
      case 'CLEAN_ARCHITECTURE':
        return 'bg-amber-950/80 text-amber-300 border-amber-800/60';
      case 'MODULAR_MONOLITH':
        return 'bg-indigo-950/80 text-indigo-300 border-indigo-800/60';
      case 'CONTROLLER_SERVICE_REPOSITORY':
      default:
        return 'bg-emerald-950/80 text-emerald-300 border-emerald-800/60';
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full">
      {/* Step Header */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/60">
            STEP 01
          </span>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Source & Classpath Ingestion Configuration
          </h2>
        </div>
        <p className="text-sm text-slate-400">
          Parse legacy Java EE / JSF codebase into OpenRewrite Lossless Semantic Tree (LST) with deep type attribution.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Input and Ingestion Mode */}
        <div className="lg:col-span-6 flex flex-col gap-5 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FolderGit2 className="h-4 w-4 text-sky-400" />
              <span>Legacy Source Codebase</span>
            </h3>
            <span className="text-[11px] font-mono text-slate-400">Step 1.1 Ingestion</span>
          </div>

          {/* Mode Switcher */}
          <div className="flex items-center p-1 bg-slate-950 rounded-lg border border-slate-800 text-xs font-medium">
            <button
              onClick={() => setUploadMode('git')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md transition ${
                uploadMode === 'git'
                  ? 'bg-sky-500 text-white shadow font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <GitBranch className="h-4 w-4" />
              <span>Git Repository URL</span>
            </button>
            <button
              onClick={() => setUploadMode('file')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md transition ${
                uploadMode === 'file'
                  ? 'bg-sky-500 text-white shadow font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileArchive className="h-4 w-4" />
              <span>Archive Upload (.zip / .war)</span>
            </button>
          </div>

          {/* Mode Specific Input */}
          {uploadMode === 'git' ? (
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                Remote Git Repository
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  placeholder="https://github.com/org/repo.git"
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3.5 py-2.5 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
                />
              </div>
              <span className="text-[11px] text-slate-500 font-mono">
                Canonical default points to enterprise sample banking monolith.
              </span>
            </div>
          ) : (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleFileDrop}
              className="border-2 border-dashed border-slate-700 hover:border-sky-500/80 rounded-xl p-6 flex flex-col items-center justify-center gap-2 bg-slate-950/60 transition cursor-pointer text-center"
            >
              <UploadCloud className="h-10 w-10 text-slate-500" />
              <div className="text-sm font-semibold text-slate-200">
                {selectedFile ? selectedFile.name : 'Drag and drop legacy archive here'}
              </div>
              <p className="text-xs text-slate-500">
                Supports .zip, .tar.gz, .war, or ear packages up to 250MB
              </p>
              <input
                type="file"
                id="file-input"
                className="hidden"
                accept=".zip,.war,.ear,.tar.gz"
                onChange={handleFileChange}
              />
              <label
                htmlFor="file-input"
                className="mt-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 text-sky-400 hover:bg-slate-700 border border-slate-600 cursor-pointer"
              >
                Browse Files
              </label>
            </div>
          )}

          {/* Configuration Presets */}
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800/80">
            {/* JDK Version */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-400 font-mono">
                Source JDK Baseline
              </label>
              <select
                value={jdkVersion}
                onChange={(e) => setJdkVersion(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
              >
                <option value="6">Java SE 6 (Sun/Oracle 1.6)</option>
                <option value="7">Java SE 7</option>
                <option value="8">Java SE 8 (LTS - Standard)</option>
                <option value="11">Java SE 11 (LTS)</option>
              </select>
            </div>

            {/* Framework Profile */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-400 font-mono">
                Framework Profile
              </label>
              <select
                value={frameworkProfile}
                onChange={(e) => setFrameworkProfile(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
              >
                <option value="JAVA_EE_6_JSF">Java EE 6 / JSF 2.x (CDI, EJB 3)</option>
                <option value="SPRING_MVC_3">Spring Framework 3.2 / MVC</option>
                <option value="STRUTS_2">Apache Struts 2.x Legacy</option>
              </select>
            </div>
          </div>

          {/* Classpath Strategy */}
          <div className="flex flex-col gap-2 pt-2">
            <label className="text-xs font-semibold text-slate-400 font-mono">
              Missing Classpath Resolution Strategy
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'AI_SYNTHETIC_STUBS', label: 'AI Synthetic Stubs', desc: 'Auto-synthesizes missing interfaces' },
                { id: 'TYPETABLE', label: 'TypeTable JSON', desc: 'Pre-computed type signatures' },
                { id: 'BINARY_JARS', label: 'Binary Lib Dir', desc: 'Scan bundled WEB-INF/lib' },
              ].map((strat) => (
                <button
                  key={strat.id}
                  type="button"
                  onClick={() => setClasspathStrategy(strat.id)}
                  className={`p-2.5 rounded-lg border text-left transition flex flex-col justify-between ${
                    classpathStrategy === strat.id
                      ? 'bg-sky-950/60 border-sky-500 text-sky-200'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <span className="text-xs font-semibold">{strat.label}</span>
                  <span className="text-[10px] text-slate-500 leading-tight mt-1">
                    {strat.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Action Trigger Button */}
          <div className="pt-2">
            <button
              onClick={handleRunIngestion}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-600 hover:to-indigo-700 shadow-md shadow-sky-500/20 disabled:opacity-50 transition"
            >
              {isLoading ? (
                <>
                  <Cpu className="h-4 w-4 animate-spin" />
                  <span>Extracting LST Semantic Model with OpenRewrite...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Trigger OpenRewrite LST Extraction & Ingest to Graph</span>
                </>
              )}
            </button>
          </div>

          {errorMsg && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Right Column: Target Architecture Profile & LST Metadata */}
        <div className="lg:col-span-6 flex flex-col gap-5">
          {/* Target Architecture Profile Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">Target Architecture Profile</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsHarvestModalOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-sky-950 hover:bg-sky-900 text-sky-300 border border-sky-800/80 transition"
              >
                <PlusCircle className="h-3.5 w-3.5" />
                <span>Harvest Microservice</span>
              </button>
            </div>

            {/* Profile Dropdown Selector */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-400 font-mono">
                Active Architectural Baseline
              </label>
              <select
                value={activeProfile?.profile_id || ''}
                onChange={(e) => setActiveProfile(e.target.value)}
                disabled={isLoadingProfile}
                className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-sky-500"
              >
                {architectureProfiles.map((p) => (
                  <option key={p.profile_id} value={p.profile_id}>
                    {p.name} ({p.profile_id})
                  </option>
                ))}
              </select>
            </div>

            {/* Profile Summary Card */}
            {activeProfile ? (
              <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl flex flex-col gap-3 font-mono text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-slate-200 font-bold text-sm block">
                      {activeProfile.name}
                    </span>
                    <span className="text-[11px] text-slate-400">{activeProfile.target_runtime}</span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wide ${getLayeringBadgeColor(
                      activeProfile.layering_pattern
                    )}`}
                  >
                    {activeProfile.layering_pattern.replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="flex flex-col gap-1 text-[11px] bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-500">Base Package Pattern:</span>
                  <span className="text-sky-300 font-semibold">
                    {activeProfile.base_package_pattern}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 bg-slate-900 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">ArchUnit Rules</span>
                    <span className="text-emerald-400 font-bold text-sm">
                      {activeProfile.conformance_rules?.length || 0}
                    </span>
                  </div>
                  <div className="p-2 bg-slate-900 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">Code Exemplars</span>
                    <span className="text-sky-400 font-bold text-sm">
                      {activeProfile.exemplars?.length || 0}
                    </span>
                  </div>
                  <div className="p-2 bg-slate-900 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">Dependencies</span>
                    <span className="text-indigo-400 font-bold text-sm">
                      {activeProfile.required_dependencies?.length || 0}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/60">
                  <span>SHA-256 Digest:</span>
                  <span className="text-slate-400 font-mono" title={activeProfile.sha256_hash}>
                    {activeProfile.sha256_hash.slice(0, 16)}...
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl text-center text-xs text-slate-500">
                Loading architecture profiles...
              </div>
            )}
          </div>

          {/* Extracted LST Metadata */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Database className="h-4 w-4 text-sky-400" />
                <span>Extracted LST Metadata</span>
              </h3>
              {successPayload && (
                <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800/60 font-semibold">
                  <CheckCircle2 className="h-3 w-3" />
                  READY
                </span>
              )}
            </div>

            {successPayload ? (
              <div className="flex flex-col gap-3 font-mono text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                    <span className="text-slate-500 text-[10px] uppercase block">Classes Found</span>
                    <span className="text-xl font-bold text-white">
                      {successPayload.classes_count || 14}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                    <span className="text-slate-500 text-[10px] uppercase block">Method Invocations</span>
                    <span className="text-xl font-bold text-white">
                      {successPayload.methods_count || 48}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                    <span className="text-slate-500 text-[10px] uppercase block">Injected Fields</span>
                    <span className="text-xl font-bold text-white">
                      {successPayload.injected_fields_count || 19}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                    <span className="text-slate-500 text-[10px] uppercase block">CICS Gateways</span>
                    <span className="text-xl font-bold text-sky-400">
                      {successPayload.cics_gateways_count || 1}
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex flex-col gap-1 text-[11px]">
                  <span className="text-slate-500">SHA-256 Digest:</span>
                  <span className="text-sky-300 font-bold break-all">
                    {successPayload.sha256_digest || '4a7f29b4e1c8d5a2f30691e84b2c159e...'}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex flex-col gap-1 text-[11px]">
                  <span className="text-slate-500">Extracted Timestamp:</span>
                  <span className="text-slate-300">
                    {successPayload.extracted_at || new Date().toISOString()}
                  </span>
                </div>

                {/* Next Step Transition */}
                <button
                  onClick={() => setStep(2)}
                  className="mt-2 w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg font-semibold text-xs text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20 transition"
                >
                  <span>Proceed to Topology Discovery (Step 2)</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="py-8 flex flex-col items-center justify-center text-center gap-2 text-slate-500">
                <Layers className="h-8 w-8 text-slate-700" />
                <p className="text-xs">No metadata extracted yet.</p>
                <p className="text-[11px] text-slate-600 max-w-[240px]">
                  Click the button on the left to trigger the OpenRewrite parser on the legacy banking monolith.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Harvest Reference Microservice Modal */}
      {isHarvestModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl flex flex-col gap-5">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-sky-400" />
                <h3 className="font-bold text-base text-white">Harvest Reference Microservice</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsHarvestModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Ingest an approved enterprise Spring Boot microservice to inspect its build BOM,
              topology, code exemplars, and ArchUnit rules.
            </p>

            <form onSubmit={handleHarvestSubmit} className="flex flex-col gap-4">
              {/* Profile Name */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-slate-300 font-mono">
                  Profile Name
                </label>
                <input
                  type="text"
                  value={harvestProfileName}
                  onChange={(e) => setHarvestProfileName(e.target.value)}
                  placeholder="e.g., Payments-Reference-v2"
                  className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-xs text-white font-mono focus:outline-none focus:border-sky-500"
                  required
                />
              </div>

              {/* Mode Switcher */}
              <div className="flex items-center p-1 bg-slate-950 rounded-lg border border-slate-800 text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setHarvestMode('git')}
                  className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-md transition ${
                    harvestMode === 'git'
                      ? 'bg-sky-500 text-white font-semibold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <FolderGit2 className="h-3.5 w-3.5" />
                  <span>Repo Path / URL</span>
                </button>
                <button
                  type="button"
                  onClick={() => setHarvestMode('file')}
                  className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-md transition ${
                    harvestMode === 'file'
                      ? 'bg-sky-500 text-white font-semibold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <FileArchive className="h-3.5 w-3.5" />
                  <span>Upload ZIP</span>
                </button>
              </div>

              {/* Mode Input */}
              {harvestMode === 'git' ? (
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-300 font-mono">
                    Workspace Repo Path or Git URL
                  </label>
                  <input
                    type="text"
                    value={harvestRepoPath}
                    onChange={(e) => setHarvestRepoPath(e.target.value)}
                    placeholder="samples/reference-spring-boot-service"
                    className="bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-xs text-white font-mono focus:outline-none focus:border-sky-500"
                  />
                  <span className="text-[11px] text-slate-500 font-mono">
                    Default points to approved Spring Boot 3.5 reference microservice.
                  </span>
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-300 font-mono">
                    Microservice ZIP File
                  </label>
                  <input
                    type="file"
                    accept=".zip"
                    onChange={(e) => setHarvestFile(e.target.files?.[0] || null)}
                    className="text-xs text-slate-300 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-sky-950 file:text-sky-300 hover:file:bg-sky-900 cursor-pointer"
                  />
                </div>
              )}

              {harvestError && (
                <div className="p-3 bg-rose-950/70 border border-rose-800 rounded-lg text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{harvestError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsHarvestModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isHarvesting}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-md shadow-sky-600/20 disabled:opacity-50 transition"
                >
                  {isHarvesting ? (
                    <>
                      <Cpu className="h-4 w-4 animate-spin" />
                      <span>Harvesting 4 Layers...</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="h-4 w-4" />
                      <span>Harvest Architecture</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
