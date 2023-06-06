from wasmtime import WasiConfig
import jit
import sys

def dump_diff_to_file(before, after, fileName):
    if len(before) != len(after):
        raise Exception("sizes aren't equal")

    with open(fileName, "wt") as outputFile:
        for i in range(len(before)):
            if before[i] != after[i]:
                outputFile.write(str(i))
                outputFile.write(' ')
                outputFile.write(str(after[i]))
                outputFile.write('\n')

if len(sys.argv) <= 1:
  raise Exception("please, specify input.js")

inputFileName = sys.argv[1]

wasiConfig = WasiConfig()
wasiConfig.inherit_stdout()
wasiConfig.inherit_stderr()

jit.initializeSpiderMonkey(wasiConfig, True)

memory_before = jit.dump_memory_to_array()

test_function_str_ptr = None
with open(inputFileName, 'r') as file:
    test_function_str_ptr = jit.write_string(file.read())

jit.execute(test_function_str_ptr)

main_function_name_ptr = jit.write_string("main")
for i in range(0, 101):
    print (f"Time in ms: {jit.callFunctionByName(main_function_name_ptr)}")

jit.patchSpiderMonkeyWithJit(True)
print (f"Time in ms: {jit.callFunctionByName(main_function_name_ptr)}")

jit.patchSpiderMonkeyWithJit(True)
print (f"Time in ms: {jit.callFunctionByName(main_function_name_ptr)}")

memory_after = jit.dump_memory_to_array()

dump_diff_to_file(memory_before, memory_after, "diff.txt")

jit.free_string(test_function_str_ptr)
jit.free_string(main_function_name_ptr)

jit.deinitializeSpiderMonkey()
