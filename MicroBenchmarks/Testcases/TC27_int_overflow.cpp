// Category: Integer Errors
// Error: Integer overflow

#include <iostream>
#include <climits>

int main() {
    int maxInt = INT_MAX;
    int result = maxInt + 1;  // ERROR: Integer overflow (undefined behavior)
    
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
