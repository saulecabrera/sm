use wasmtime::*;
use wasmtime_wasi::{WasiCtx, WasiCtxBuilder};
use criterion::{criterion_group, criterion_main, Criterion, black_box};
use std::collections::HashMap;
use std::path::Path;
use std::fs::File;
use std::io::{self, BufRead};
use std::time::{Instant, Duration};

fn js(c: &mut Criterion) {
    let engine = Engine::default();

    let wasi = WasiCtxBuilder::new()
        .inherit_stdio()
        .build();

    let sm_memory_diff = read_diff(&Path::new("benches/diff.txt"));
    let sm_engine = Module::from_binary(&engine, include_bytes!("./spiderMonkey.wasm")).unwrap();
    let sm_jit_module = Module::from_binary(&engine, include_bytes!("./jitmodule.wasm")).unwrap();
    let javy_module = Module::from_binary(&engine, include_bytes!("./javy.wasm")).unwrap();
    let rust_module = Module::from_binary(&engine, include_bytes!("./rust.wasm")).unwrap();

    let mut group = c.benchmark_group("JS Execution");

    group.bench_function("Sum: QuickJS (interpreted)", |b| {
        b.iter_custom(|iters| {
            let mut total_duration = Duration::new(0, 0);
            for _ in 0..iters {
                let (linker, mut store) = setup_store(&engine, &wasi);
                let instance = linker.instantiate(&mut store, &javy_module).unwrap();
                let f = instance.get_typed_func::<(), ()>(&mut store, "_start").unwrap();
                let start = Instant::now();
                f.call(&mut store, ()).unwrap();
                let end = Instant::now();
                total_duration += end - start;
            }
            total_duration
        });
    });

    group.bench_function("Sum: SpiderMonkey (AOT)", |b| {
        b.iter_custom(|iters| {
            let mut total_duration = Duration::new(0, 0);
            for _ in 0..iters {
                let (mut linker, mut store) = setup_store(&engine, &wasi);
                let sm_instance = linker.instantiate(&mut store, &sm_engine).unwrap();
                let sm_exports = get_sm_exports(&mut store, &sm_instance);
                linker.instance(&mut store, "env", sm_instance).unwrap();

                 sm_exports.init.call(&mut store, ()).unwrap();
                 sm_exports.init_vm.call(&mut store, 1).unwrap();

                 let _jit_module_instance = linker.instantiate(&mut store, &sm_jit_module).unwrap();
                 patch_memory(&mut store, &sm_instance, &sm_memory_diff);


                 let start = Instant::now();
                 let zero = sm_exports.main.call(&mut store, (0, 1)).unwrap();
                 let end = Instant::now();
                 assert_eq!(zero, 0f64);
                 // total_duration += Duration::from_micros(taken as u64);
                 total_duration += end - start;

            }
            total_duration
        });
    });

    group.bench_function("Sum: Rust", |b| {
        b.iter_custom(|iters| {
            let mut total_duration = Duration::new(0, 0);
            for _ in 0..iters {
                let (linker, mut store) = setup_store(&engine, &wasi);
                let instance = linker.instantiate(&mut store, &rust_module).unwrap();
                let f = instance.get_typed_func::<(), ()>(&mut store, "_start").unwrap();
                let start = Instant::now();
                f.call(&mut store, ()).unwrap();
                let end = Instant::now();
                total_duration += end - start;
            }
            total_duration
        });
    });

    group.finish();
}

fn get_sm_exports(mut store: impl AsContextMut, instance: &Instance) -> SMExports {
    SMExports {
        init: instance.get_typed_func::<(), ()>(store.as_context_mut(), "_initialize").unwrap(),
        init_vm: instance.get_typed_func::<i32, ()>(store.as_context_mut(), "InitializeSM").unwrap(),
        main: instance.get_typed_func::<(i32, i32), f64>(store.as_context_mut(), "CallMain").unwrap(),
    }
}

struct SMExports {
    init: TypedFunc<(), ()>,
    init_vm: TypedFunc<i32, ()>,
    main: TypedFunc<(i32, i32), f64>,
}

fn setup_store(engine: &Engine, wasi: &WasiCtx) -> (Linker<WasiCtx>, Store<WasiCtx>) {
    let mut linker: Linker<WasiCtx> = Linker::new(&engine);
    wasmtime_wasi::add_to_linker(&mut linker, |s| s).unwrap();
    (linker, Store::new(&engine, wasi.clone()))
}

fn patch_memory(mut store: impl AsContextMut, instance: &Instance, diff: &HashMap<usize, u8>) {
    let memory = instance.get_memory(store.as_context_mut(), "memory").unwrap();
    let data = memory.data_mut(store.as_context_mut());

    for (k, v) in diff.iter() {
        data[*k] = *v;
    }
}

fn read_diff(path: &Path) -> HashMap<usize, u8> {
    let file = File::open(path).unwrap();
    let reader = io::BufReader::new(file);
    let mut map = HashMap::new();

    for line in reader.lines() {
        let line = line.unwrap();
        let parts: Vec<&str> = line.split_whitespace().collect();

        assert!(parts.len() == 2);
        let key = parts[0].parse::<usize>().unwrap();
        let value = parts[1].parse::<u8>().unwrap();
        map.insert(key, value);
    }
    map
}


criterion_group!(benches, js);
criterion_main!(benches);
