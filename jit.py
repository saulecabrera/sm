from wasmtime import Engine, Store, Module, Instance, Func, FuncType, Linker, WasiConfig, Config, Global, GlobalType, ValType, Val
import wasmtime.loader
import spiderMonkey
import os

jitModuleCount = 0
NUM_REGS = 7

engine = Engine()
spiderMonkeyModule = Module.from_file(engine, "./spiderMonkey.wasm")
linker = None
store = Store(engine)
spiderMonkey = None

def initializeSpiderMonkey(config, enableCacheIR = False):
    global spiderMonkeyModule
    global spiderMonkey
    global store
    global linker

    store.set_wasi(config)

    linker = Linker(engine)
    linker.define_wasi()

    globalTypeForRegister = GlobalType(ValType.i32(), True)
    for i in range(NUM_REGS):
        linker.define(store, "env", "r" + str(i + 1), Global(store, globalTypeForRegister, Val.i32(0)))

    spiderMonkey = linker.instantiate(store, spiderMonkeyModule)

    linker.define(store, "env", "memory", spiderMonkey.exports(store)["memory"])
    linker.define(store, "env", "__indirect_function_table", spiderMonkey.exports(store)["__indirect_function_table"])
    linker.define(store, "env", "__stack_pointer", spiderMonkey.exports(store)["__stack_pointer"])

    # Explicitly initialize, as we build hw as a WASI reactor, not a
    # WASI command.
    spiderMonkey.exports(store)["_initialize"](store)

    # Initialize internal vm state
    spiderMonkey.exports(store)["InitializeSM"](store, enableCacheIR)

def deinitializeSpiderMonkey():
    global spiderMonkey
    global store

    # ShutDownSM internal vm state
    spiderMonkey.exports(store)["ShutDownSM"](store)

def execute(text_ptr):
    global spiderMonkey
    global store
    spiderMonkey.exports(store)["Execute"](store, text_ptr)

def callFunctionByName(text_ptr):
    global spiderMonkey
    global store
    return spiderMonkey.exports(store)["CallFunctionByName"](store, text_ptr, True, True)

def write_string(string):
    utf8 = string.encode('utf-8')
    ptr = spiderMonkey.exports(store)["AllocateBytes"](store, len(utf8) + 1)
    dst = spiderMonkey.exports(store)["memory"].data_ptr(store)
    for i in range(0, len(utf8)):
        dst[ptr + i] = utf8[i]
    dst[ptr + len(utf8)] = 0
    return ptr

def free_string(ptr):
    spiderMonkey.exports(store)["FreeBytes"](store, ptr)

def jitModule(applyWasmOpt):
    global jitModuleCount
    global spiderMonkey
    global store
    global engine

    ptr = spiderMonkey.exports(store)["jitModule"](store)
    if ptr == 0:
        return None

    data = spiderMonkey.exports(store)["moduleData"](store, ptr)
    size = spiderMonkey.exports(store)["moduleSize"](store, ptr)
    dst = bytearray()
    src = spiderMonkey.exports(store)["memory"].data_ptr(store)
    for i in range(0, size):
        dst.append(src[data + i])
    dumpWasmFileName = "jitmodule" + str(jitModuleCount) + ".wasm"
    dumpFile = open(dumpWasmFileName, "wb")
    dumpFile.write(dst)
    dumpFile.close()
    spiderMonkey.exports(store)["freeModule"](store, ptr)

    if applyWasmOpt:
        dumpWasmOptimizedFileName = "jitmodule_opt_" + str(jitModuleCount) + ".wasm"
        os.system('wasm-opt -O4 --enable-reference-types --inlining-optimizing --always-inline-max-function-size 400 ' + dumpWasmFileName + ' -o ' + dumpWasmOptimizedFileName)
        optFile = open(dumpWasmOptimizedFileName, "rb")
        dst = bytearray(optFile.read())
        optFile.close()

    module = Module(engine, dst)
    dumpFile = open("dump" + str(jitModuleCount), "wb")
    dumpFile.write(module.serialize())
    dumpFile.close()
    return module

def patchSpiderMonkeyWithJit(applyWasmOpt = False):
    global jitModuleCount
    global store
    global linker

    print('Calling jitModule()')
    jit_module = jitModule(applyWasmOpt)
    print(f'jitModule result: {jit_module}')

    if jit_module is not None:
        print(f'Instantiating and patching in JIT module')
        linker.instantiate(store, jit_module)
        jitModuleCount = jitModuleCount + 1

def instantiateModule(bytes):
    global spiderMonkey
    global store
    global engine

    module = Module(engine, bytes)
    linker.instantiate(store, module)

def dump_memory(fileName):
    global spiderMonkey
    global store

    memoryObject = spiderMonkey.exports(store)["memory"]
    sizeInBytes = memoryObject.size(store) * 64 * 1024
    memoryBytes = bytearray([])
    for i in range(sizeInBytes):
        memoryBytes.append(memoryObject.data_ptr(store)[i])

    print("size of memory ", len(memoryBytes))
    with open(fileName, "wb") as outputFile:
        outputFile.write(bytes(memoryBytes))

def dump_memory_to_array():
    global spiderMonkey
    global store

    memoryObject = spiderMonkey.exports(store)["memory"]
    sizeInBytes = memoryObject.size(store) * 64 * 1024
    memoryBytes = bytearray([])
    for i in range(sizeInBytes):
        memoryBytes.append(memoryObject.data_ptr(store)[i])

    return memoryBytes

def install_memory_from_diff(diffDict):
    global spiderMonkey
    global store

    memoryObject = spiderMonkey.exports(store)["memory"]
    for i, val in diffDict.items():
        memoryObject.data_ptr(store)[i] = val


