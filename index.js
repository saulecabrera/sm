function sum(obj) {
  let result = 0;
  for (let i = 0; i <= obj.n; ++i) {
    result += i;
  }
  return result;
}

function main() {
  var payload = {
    "n": 50000
  };

  return sum({n: payload.n});
}
