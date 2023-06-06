from wasmtime import WasiConfig
import jit
import sys

def read_diff_from_file(fileName):
    dict = {}
    with open(fileName, "rt") as file:
        for line in file:
            list = line.split()
            dict[int(list[0])] = int(list[1])
    return dict

def read_module_from_file(fileName):
    bytes = bytearray()
    with open(fileName, "rb") as file:
        bytes = bytearray(file.read())
    return bytes

if len(sys.argv) <= 3:
  raise Exception("please, specify diff.txt jit1.wasm jit2.wasm")

diffFileName = sys.argv[1]
jitcodeFileName1 = sys.argv[2]
jitcodeFileName2 = sys.argv[3]

wasiConfig = WasiConfig()
wasiConfig.inherit_stdout()
wasiConfig.inherit_stderr()

jit.initializeSpiderMonkey(wasiConfig, True)

# instantiate jit modules
jit.instantiateModule(read_module_from_file(jitcodeFileName1))
jit.instantiateModule(read_module_from_file(jitcodeFileName2))

# patch memory
jit.install_memory_from_diff(read_diff_from_file(diffFileName))

main_function_name_ptr = jit.write_string("main")
print (f"Time in ms: {jit.callFunctionByName(main_function_name_ptr)}")

jit.free_string(main_function_name_ptr)

jit.deinitializeSpiderMonkey()
